from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.connectors.github.errors import GitHubNotConnected
from app.connectors.github.schemas import CreateGitHubIssueAction, RequestPullRequestReviewAction
from app.connectors.github.service import GitHubService
from app.connectors.notion.action_items import NotionActionItemPropertyMapping
from app.connectors.notion.schemas import CreateNotionTaskAction
from app.documents.base import FileStore
from app.documents.errors import DocumentParseFailed
from app.documents.models import UploadedDocument
from app.documents.service import DocumentService
from app.domain.enums import ActionProvider, ActionStatus, ConnectionStatus, Provider
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import DomainError, UnauthorizedResourceAccess
from app.models.entities import (
    ProjectWorkspace,
    ProposedAction,
    SourceDocument,
    WorkflowDefinition,
    WorkflowRun,
)
from app.repositories.relay import RelayRepository
from app.schemas.domain import ApprovalRead, RunInput, RunRead
from app.services.audit import record
from app.services.workflows import WorkflowService
from app.workflows.project_meeting.actions import (
    CREATE_GITHUB_ISSUE_OPERATION,
    NOTION_TASK_OPERATION,
    REQUEST_GITHUB_PR_REVIEW_OPERATION,
    ActionPlanner,
    PlannedAction,
    build_github_issue_action,
    build_notion_task_action,
    build_pull_request_review_action,
)
from app.workflows.project_meeting.analysis import MeetingAnalysisService
from app.workflows.project_meeting.errors import (
    ActionItemsUnresolved,
    CollaborateWorkflowInvalidState,
    ProjectRequired,
)
from app.workflows.project_meeting.identity import member_by_id
from app.workflows.project_meeting.transcript import MeetingTranscript, parse_transcript


class ProjectMeetingWorkflowService:
    def __init__(
        self,
        repo: RelayRepository,
        documents: DocumentService,
        store: FileStore,
        analysis: MeetingAnalysisService,
        github: GitHubService,
        provider_name: str,
    ):
        self.repo, self.session = repo, repo.session
        self.documents, self.store, self.analysis = documents, store, analysis
        self.github = github
        self.provider_name = provider_name
        self.workflow = WorkflowService(repo)

    async def owned_run(self, run_id: UUID, owner: UUID, *, lock: bool = False) -> WorkflowRun:
        run = await self.repo.run(run_id, owner, lock=lock)
        definition = await self.session.get(WorkflowDefinition, run.workflow_definition_id)
        if definition is None or definition.key != "project_meeting":
            raise UnauthorizedResourceAccess()
        return run

    async def create(self, owner: UUID, project_id: UUID) -> RunRead:
        project = await self.repo.project(project_id, owner)
        definition = await self.session.scalar(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.key == "project_meeting")
            .order_by(WorkflowDefinition.version.desc())
        )
        if definition is None:
            raise UnauthorizedResourceAccess()
        run_data = await self.workflow.create(owner, RunInput(workflow_definition_id=definition.id))
        run = await self.repo.run(run_data.id, owner, lock=True)
        run.project_workspace_id = project.id
        await self.session.commit()
        return RunRead.model_validate(run)

    async def source(self, run_id: UUID, owner: UUID) -> SourceDocument:
        await self.owned_run(run_id, owner)
        source = await self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.workflow_run_id == run_id, SourceDocument.user_id == owner
            )
        )
        if source is None:
            raise UnauthorizedResourceAccess()
        return source

    async def project(self, run: WorkflowRun, owner: UUID) -> ProjectWorkspace:
        if run.project_workspace_id is None:
            raise ProjectRequired()
        return await self.repo.project(run.project_workspace_id, owner)

    async def upload(
        self, run_id: UUID, owner: UUID, filename: str, content_type: str, content: bytes
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise CollaborateWorkflowInvalidState()
        file = self.documents.validate(filename, content_type, content)
        checksum = sha256(content).hexdigest()
        existing = await self.session.scalar(
            select(SourceDocument).where(SourceDocument.workflow_run_id == run_id)
        )
        if existing:
            if existing.checksum == checksum:
                return await self.detail(run_id, owner)
            raise CollaborateWorkflowInvalidState()
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
            record(
                self.session,
                owner,
                "TRANSCRIPT_UPLOADED",
                run.id,
                {"document_id": str(source.id), "size_bytes": len(content)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.store.delete(key)
            raise
        return await self.detail(run_id, owner)

    async def parse(
        self, run_id: UUID, owner: UUID, *, meeting_date: date | None = None
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise CollaborateWorkflowInvalidState()
        source = await self.source(run_id, owner)
        await self.workflow.apply_transition(run, S.ANALYZING, owner)
        record(self.session, owner, "ANALYSIS_STARTED", run.id)
        await self.session.commit()
        try:
            content = await self.store.read(source.storage_key)
            if sha256(content).hexdigest() != source.checksum:
                raise DocumentParseFailed()
            parsed = await self.documents.parse(
                UploadedDocument(source.original_filename, source.content_type, content)
            )
            raw_text = "\n\n".join(section.text for section in parsed.sections)
            transcript = parse_transcript(raw_text)
            source.parsed_payload = parsed.model_dump(mode="json")
            source.status = "PARSED"
            run.plan_payload = {
                "stage": "transcript_ready",
                "transcript": transcript.model_dump(mode="json"),
                "meeting_date": (meeting_date or datetime.now(UTC).date()).isoformat(),
                "provider": self.provider_name,
            }
            record(
                self.session,
                owner,
                "TRANSCRIPT_PARSED",
                run.id,
                {"segment_count": len(transcript.segments)},
            )
            await self.session.commit()
        except DomainError as error:
            source.status = "FAILED"
            await self.fail(run, owner, error, "ANALYSIS_FAILED")
            raise
        return await self.detail(run_id, owner)

    async def analyze(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.ANALYZING or (run.plan_payload or {}).get("stage") != "transcript_ready":
            raise CollaborateWorkflowInvalidState()
        project = await self.project(run, owner)
        members = list(await self.repo.members(project.id))
        transcript = MeetingTranscript.model_validate((run.plan_payload or {})["transcript"])
        meeting_date = date.fromisoformat((run.plan_payload or {})["meeting_date"])
        # Persist the claimed stage before the slow model call, like LEARN's
        # summarize(): a duplicate request is refused rather than re-billed.
        run.plan_payload = {**(run.plan_payload or {}), "stage": "analyzing"}
        record(self.session, owner, "MEETING_ANALYSIS_STARTED", run.id)
        await self.session.commit()
        try:
            analysis = await self.analysis.generate(transcript)
        except Exception as error:
            safe = error if isinstance(error, DomainError) else DomainError()
            await self.fail(run, owner, safe, "ANALYSIS_FAILED")
            raise safe from error
        run = await self.owned_run(run_id, owner, lock=True)
        planned = ActionPlanner().plan(analysis, members, project, meeting_date=meeting_date)
        run.plan_payload = {
            **(run.plan_payload or {}),
            "stage": "plan_ready",
            "analysis": analysis.model_dump(mode="json"),
            "action_items": [item.model_dump(mode="json") for item in planned],
        }
        record(
            self.session,
            owner,
            "MEETING_ANALYSIS_COMPLETED",
            run.id,
            {"decision_count": len(analysis.decisions), "action_item_count": len(planned)},
        )
        await self.workflow.apply_transition(run, S.PLAN_READY, owner)
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def update_action_items(
        self, run_id: UUID, owner: UUID, items: tuple[PlannedAction, ...]
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.PLAN_READY:
            raise CollaborateWorkflowInvalidState()
        run.plan_payload = {
            **(run.plan_payload or {}),
            "action_items": [item.model_dump(mode="json") for item in items],
        }
        record(self.session, owner, "ACTION_ITEM_EDITED", run.id, {"action_item_count": len(items)})
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def request_approval(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.PLAN_READY:
            raise CollaborateWorkflowInvalidState()
        project = await self.project(run, owner)
        members = list(await self.repo.members(project.id))
        drafts = [
            PlannedAction.model_validate(item)
            for item in (run.plan_payload or {}).get("action_items", [])
        ]
        mapping = (
            NotionActionItemPropertyMapping.model_validate(project.notion_property_mapping)
            if project.notion_property_mapping
            else NotionActionItemPropertyMapping(title="Name")
        )
        notion_connection_id = await self._connected_id(owner, Provider.NOTION)
        github_connection_id = await self._connected_id(owner, Provider.GITHUB)
        valid_assignees, valid_labels = await self._github_repository_facts(owner, project)

        actions: list[ProposedAction] = []
        skipped: list[dict[str, Any]] = []
        for draft in drafts:
            member = member_by_id(members, draft.member_id)
            owner_display = member.display_name if member else None
            for destination in draft.destinations:
                if destination == "notion":
                    if not project.notion_database_id:
                        skipped.append({"action_id": draft.id, "reason": "NOTION_DATABASE_NOT_SET"})
                        continue
                    payload = build_notion_task_action(
                        draft,
                        database_id=project.notion_database_id,
                        mapping=mapping,
                        connection_id=notion_connection_id,
                        owner_display_name=owner_display,
                    )
                    actions.append(
                        self._proposed_action(
                            run.id, ActionProvider.NOTION, NOTION_TASK_OPERATION, payload
                        )
                    )
                elif destination == "github":
                    if not (project.github_repository_owner and project.github_repository_name):
                        skipped.append(
                            {"action_id": draft.id, "reason": "GITHUB_REPOSITORY_NOT_SET"}
                        )
                        continue
                    if draft.category == "REVIEW_REQUEST":
                        reviewer = member.github_username if member else None
                        review_payload = (
                            build_pull_request_review_action(
                                draft,
                                repository_owner=project.github_repository_owner,
                                repository_name=project.github_repository_name,
                                reviewer_username=reviewer,
                                connection_id=github_connection_id,
                            )
                            if reviewer
                            else None
                        )
                        if review_payload is None:
                            skipped.append(
                                {"action_id": draft.id, "reason": "REVIEW_REQUEST_UNRESOLVED"}
                            )
                            continue
                        actions.append(
                            self._proposed_action(
                                run.id,
                                ActionProvider.GITHUB,
                                REQUEST_GITHUB_PR_REVIEW_OPERATION,
                                review_payload,
                            )
                        )
                    else:
                        assignee = member.github_username if member else None
                        issue_payload = build_github_issue_action(
                            draft,
                            repository_owner=project.github_repository_owner,
                            repository_name=project.github_repository_name,
                            assignee_username=assignee if assignee in valid_assignees else None,
                            connection_id=github_connection_id,
                        )
                        issue_payload = issue_payload.model_copy(
                            update={
                                "labels": tuple(
                                    label for label in issue_payload.labels if label in valid_labels
                                )
                            }
                        )
                        actions.append(
                            self._proposed_action(
                                run.id,
                                ActionProvider.GITHUB,
                                CREATE_GITHUB_ISSUE_OPERATION,
                                issue_payload,
                            )
                        )
        if not actions:
            raise ActionItemsUnresolved()
        for action in actions:
            self.session.add(action)
        await self.session.flush()
        for action in actions:
            record(
                self.session,
                owner,
                "PROPOSED_ACTION_CREATED",
                run.id,
                {"action_id": str(action.id), "action_type": action.action_type},
            )
        if skipped:
            record(self.session, owner, "ACTION_ITEMS_SKIPPED", run.id, {"skipped": skipped})
        await self.workflow.request_approvals(run.id, owner)
        record(
            self.session,
            owner,
            "PLAN_APPROVAL_REQUESTED",
            run.id,
            {"action_count": len(actions), "skipped_count": len(skipped)},
        )
        await self.session.commit()
        return await self.detail(run_id, owner)

    def _proposed_action(
        self,
        run_id: UUID,
        provider: ActionProvider,
        action_type: str,
        payload: CreateNotionTaskAction | CreateGitHubIssueAction | RequestPullRequestReviewAction,
    ) -> ProposedAction:
        return ProposedAction(
            workflow_run_id=run_id,
            provider=provider,
            action_type=action_type,
            payload=payload.model_dump(mode="json"),
            status=ActionStatus.PROPOSED,
        )

    async def _connected_id(self, owner: UUID, provider: Provider) -> str | None:
        connections = [
            item
            for item in await self.repo.connections(owner, provider)
            if item.status == ConnectionStatus.CONNECTED
        ]
        return str(connections[0].id) if connections else None

    async def _github_repository_facts(
        self, owner: UUID, project: ProjectWorkspace
    ) -> tuple[set[str], set[str]]:
        """Best-effort live validation (section 11): assignees/labels the
        model or user proposed are dropped, never sent, if they don't
        actually exist on the repository. Connection or repository problems
        here just mean nothing validates -- the action items still get
        created, without an assignee or those labels, rather than blocking
        the whole approval round."""
        if not (project.github_repository_owner and project.github_repository_name):
            return set(), set()
        try:
            collaborators = await self.github.collaborators(
                owner, project.github_repository_owner, project.github_repository_name
            )
            labels = await self.github.labels(
                owner, project.github_repository_owner, project.github_repository_name
            )
        except (GitHubNotConnected, DomainError):
            return set(), set()
        return {item.login for item in collaborators}, {item.name for item in labels}

    async def fail(self, run: WorkflowRun, owner: UUID, error: DomainError, event: str) -> None:
        run.error_code, run.error_message = error.code, error.message
        record(self.session, owner, event, run.id, {"error_code": error.code})
        await self.workflow.apply_transition(run, S.FAILED, owner)
        await self.session.commit()

    async def detail(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner)
        source = await self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.workflow_run_id == run_id, SourceDocument.user_id == owner
            )
        )
        approvals = await self.repo.run_approvals(run_id)
        project = None
        if run.project_workspace_id is not None:
            try:
                project = await self.repo.project(run.project_workspace_id, owner)
            except UnauthorizedResourceAccess:
                project = None
        payload = run.plan_payload or {}
        return {
            "run": RunRead.model_validate(run).model_dump(mode="json"),
            "project": {
                "id": str(project.id),
                "name": project.name,
                "course": project.course,
                "notion_database_id": project.notion_database_id,
                "github_repository_owner": project.github_repository_owner,
                "github_repository_name": project.github_repository_name,
            }
            if project
            else None,
            "source": None
            if source is None
            else {
                "id": str(source.id),
                "filename": source.original_filename,
                "content_type": source.content_type,
                "size_bytes": source.size_bytes,
                "status": source.status,
            },
            "stage": payload.get("stage"),
            "summary": (payload.get("analysis") or {}).get("summary"),
            "decisions": (payload.get("analysis") or {}).get("decisions", []),
            "unresolved_questions": (payload.get("analysis") or {}).get("unresolved_questions", []),
            "action_items": payload.get("action_items", []),
            "approvals": [
                ApprovalRead.model_validate(item).model_dump(mode="json") for item in approvals
            ],
        }
