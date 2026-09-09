from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.documents.base import FileStore
from app.documents.models import ParsedDocument, UploadedDocument
from app.documents.service import DocumentService
from app.domain.enums import (
    ActionProvider,
    ActionStatus,
    ApprovalStatus,
    ConnectionStatus,
    Provider,
)
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import ApprovalPayloadMismatch, DomainError, UnauthorizedResourceAccess
from app.models.entities import (
    ExternalArtifact,
    ProposedAction,
    SourceDocument,
    WorkflowDefinition,
    WorkflowRun,
)
from app.repositories.relay import RelayRepository
from app.schemas.domain import ApprovalRead, RunInput, RunRead
from app.services.approvals import exact_json
from app.services.audit import record
from app.services.workflows import WorkflowService
from app.workflows.lecture_notes.actions import OPERATION, proposed_page
from app.workflows.lecture_notes.errors import (
    LearnWorkflowInvalidState,
    SummaryGenerationFailed,
)
from app.workflows.lecture_notes.schemas import LectureSummary
from app.workflows.lecture_notes.summarization import SummaryService, validate_references


class LectureNotesWorkflowService:
    def __init__(
        self,
        repo: RelayRepository,
        documents: DocumentService,
        store: FileStore,
        summaries: SummaryService,
        provider_name: str,
    ):
        self.repo, self.session = repo, repo.session
        self.documents, self.store, self.summaries = documents, store, summaries
        self.provider_name = provider_name
        self.workflow = WorkflowService(repo)

    async def owned_run(self, run_id: UUID, owner: UUID, *, lock: bool = False) -> WorkflowRun:
        run = await self.repo.run(run_id, owner, lock=lock)
        definition = await self.session.get(WorkflowDefinition, run.workflow_definition_id)
        if definition is None or definition.key != "lecture_to_notion":
            raise UnauthorizedResourceAccess()
        return run

    async def create(self, owner: UUID) -> RunRead:
        definition = await self.session.scalar(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.key == "lecture_to_notion",
            )
            .order_by(WorkflowDefinition.version.desc())
        )
        if definition is None:
            raise UnauthorizedResourceAccess()
        return await self.workflow.create(owner, RunInput(workflow_definition_id=definition.id))

    async def source(self, run_id: UUID, owner: UUID) -> SourceDocument:
        await self.owned_run(run_id, owner)
        source = await self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.workflow_run_id == run_id,
                SourceDocument.user_id == owner,
            )
        )
        if source is None:
            raise UnauthorizedResourceAccess()
        return source

    async def artifact(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner)
        artifact = await self.session.scalar(
            select(ExternalArtifact).where(ExternalArtifact.workflow_run_id == run.id)
        )
        if artifact is None:
            raise UnauthorizedResourceAccess()
        return {
            "id": str(artifact.id),
            "provider": artifact.provider,
            "artifact_type": artifact.artifact_type,
            "external_id": artifact.external_id,
            "external_url": artifact.external_url,
            "created_at": artifact.created_at.isoformat(),
        }

    async def upload(
        self,
        run_id: UUID,
        owner: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise LearnWorkflowInvalidState()
        file = self.documents.validate(filename, content_type, content)
        checksum = sha256(content).hexdigest()
        existing = await self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.workflow_run_id == run_id,
            )
        )
        if existing:
            if existing.checksum == checksum:
                return await self.detail(run_id, owner)
            raise LearnWorkflowInvalidState()
        key = await self.store.save(content)
        source = SourceDocument(
            user_id=owner,
            workflow_run_id=run.id,
            original_filename=file.filename,
            content_type=file.content_type,
            size_bytes=len(content),
            storage_key=key,
            checksum=checksum,
        )
        try:
            self.session.add(source)
            await self.session.flush()
            for event in ["DOCUMENT_UPLOADED", "DOCUMENT_VALIDATED"]:
                record(
                    self.session,
                    owner,
                    event,
                    run.id,
                    {
                        "document_id": str(source.id),
                        "size_bytes": len(content),
                        "content_type": file.content_type,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.store.delete(key)
            raise
        return await self.detail(run_id, owner)

    async def parse(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise LearnWorkflowInvalidState()
        source = await self.source(run_id, owner)
        await self.workflow.apply_transition(run, S.ANALYZING, owner)
        record(self.session, owner, "DOCUMENT_PARSE_STARTED", run.id)
        await self.session.commit()
        try:
            content = await self.store.read(source.storage_key)
            if sha256(content).hexdigest() != source.checksum:
                from app.documents.errors import DocumentParseFailed

                raise DocumentParseFailed()
            parsed = await self.documents.parse(
                UploadedDocument(
                    source.original_filename,
                    source.content_type,
                    content,
                )
            )
            source.parsed_payload = parsed.model_dump(mode="json")
            source.status = "PARSED"
            record(
                self.session,
                owner,
                "DOCUMENT_PARSED",
                run.id,
                {
                    "section_count": len(parsed.sections),
                    "page_count": parsed.metadata.page_count,
                    "parser": parsed.metadata.parser,
                },
            )
            await self.session.commit()
        except DomainError as error:
            source.status = "FAILED"
            await self.fail(run, owner, error, "DOCUMENT_PARSE_FAILED")
            raise
        return await self.detail(run_id, owner)

    async def summarize(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.ANALYZING or run.plan_payload is not None:
            raise LearnWorkflowInvalidState()
        source = await self.source(run_id, owner)
        if source.status != "PARSED" or source.parsed_payload is None:
            raise LearnWorkflowInvalidState()
        # Persist the claimed stage before the slow provider call; duplicate requests are refused.
        run.plan_payload = {"stage": "summarizing", "provider": self.provider_name}
        parsed = ParsedDocument.model_validate(source.parsed_payload)
        record(
            self.session,
            owner,
            "SUMMARY_GENERATION_STARTED",
            run.id,
            {
                "strategy": self.summaries.strategy(parsed),
                "provider": self.provider_name,
            },
        )
        await self.session.commit()
        try:
            summary = await self.summaries.generate(parsed)
        except Exception as error:
            safe = error if isinstance(error, DomainError) else SummaryGenerationFailed()
            await self.fail(run, owner, safe, "SUMMARY_GENERATION_FAILED")
            raise safe from error
        run = await self.owned_run(run_id, owner, lock=True)
        run.plan_payload = {
            "summary": summary.model_dump(mode="json"),
            "provider": self.provider_name,
            "strategy": self.summaries.strategy(parsed),
        }
        record(self.session, owner, "SUMMARY_GENERATED", run.id)
        await self.workflow.apply_transition(run, S.PLAN_READY, owner)
        action = ProposedAction(
            workflow_run_id=run.id,
            provider=ActionProvider.NOTION,
            action_type=OPERATION,
            payload=await self.destination_payload(summary, owner),
        )
        self.session.add(action)
        await self.session.flush()
        record(
            self.session, owner, "PROPOSED_ACTION_CREATED", run.id, {"action_id": str(action.id)}
        )
        await self.workflow.request_approvals(run.id, owner)
        return await self.detail(run_id, owner)

    async def edit(
        self,
        run_id: UUID,
        owner: UUID,
        summary: LectureSummary,
        expected_payload: dict[str, Any],
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.AWAITING_APPROVAL:
            raise LearnWorkflowInvalidState()
        source = await self.source(run_id, owner)
        validate_references(summary, ParsedDocument.model_validate(source.parsed_payload))
        approvals = await self.repo.run_approvals(run_id)
        actions = await self.repo.actions(run_id)
        if len(approvals) != 1 or len(actions) != 1:
            raise LearnWorkflowInvalidState()
        approval, action = approvals[0], actions[0]
        if approval.status != ApprovalStatus.PENDING:
            raise LearnWorkflowInvalidState()
        if exact_json(expected_payload) != exact_json(action.payload):
            raise ApprovalPayloadMismatch()
        payload = await self.destination_payload(summary, owner)
        action.payload, action.status = payload, ActionStatus.EDITED
        approval.original_payload = payload
        run.plan_payload = {**(run.plan_payload or {}), "summary": summary.model_dump(mode="json")}
        record(self.session, owner, "ACTION_EDITED", run.id, {"action_id": str(action.id)})
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def update_destination(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.AWAITING_APPROVAL:
            raise LearnWorkflowInvalidState()
        summary_data = (run.plan_payload or {}).get("summary")
        if summary_data is None:
            raise LearnWorkflowInvalidState()
        approvals = await self.repo.run_approvals(run_id)
        actions = await self.repo.actions(run_id)
        if len(approvals) != 1 or len(actions) != 1:
            raise LearnWorkflowInvalidState()
        approval, action = approvals[0], actions[0]
        if approval.status != ApprovalStatus.PENDING:
            raise LearnWorkflowInvalidState()
        payload = await self.destination_payload(LectureSummary.model_validate(summary_data), owner)
        action.payload, approval.original_payload = payload, payload
        record(self.session, owner, "NOTION_DESTINATION_SELECTED", run.id)
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def destination_payload(self, summary: LectureSummary, owner: UUID) -> dict[str, Any]:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.NOTION)
            if item.status == ConnectionStatus.CONNECTED
        ]
        connection = connections[0] if connections else None
        metadata = connection.provider_metadata if connection else {}
        return proposed_page(
            summary,
            connection_id=str(connection.id) if connection else None,
            destination_id=metadata.get("default_destination_id") if metadata else None,
            destination_title=metadata.get("default_destination_title") if metadata else None,
            workspace_id=metadata.get("workspace_id") if metadata else None,
            workspace_name=metadata.get("workspace_name") if metadata else None,
        ).model_dump(mode="json")

    async def fail(self, run: WorkflowRun, owner: UUID, error: DomainError, event: str) -> None:
        run.error_code, run.error_message = error.code, error.message
        record(self.session, owner, event, run.id, {"error_code": error.code})
        await self.workflow.apply_transition(run, S.FAILED, owner)
        await self.session.commit()

    async def detail(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner)
        source = await self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.workflow_run_id == run_id,
                SourceDocument.user_id == owner,
            )
        )
        approvals = await self.repo.run_approvals(run_id)
        return {
            "run": RunRead.model_validate(run).model_dump(mode="json"),
            "source": None
            if source is None
            else {
                "id": str(source.id),
                "filename": source.original_filename,
                "content_type": source.content_type,
                "size_bytes": source.size_bytes,
                "checksum": source.checksum,
                "status": source.status,
                "metadata": source.parsed_payload["metadata"] if source.parsed_payload else None,
                "sections": [
                    {k: v for k, v in section.items() if k != "text"}
                    for section in source.parsed_payload["sections"]
                ]
                if source.parsed_payload
                else [],
            },
            "summary": (run.plan_payload or {}).get("summary"),
            "provider": (run.plan_payload or {}).get("provider", self.provider_name),
            "stage": (run.plan_payload or {}).get("stage"),
            "approval": ApprovalRead.model_validate(approvals[0]).model_dump(mode="json")
            if approvals
            else None,
            "destination": (approvals[0].original_payload if approvals else {}).get(
                "parent_destination_title"
            )
            if approvals
            else None,
        }
