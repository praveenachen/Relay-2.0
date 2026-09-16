from copy import deepcopy
from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.enums import ActionProvider, ActionStatus, ApprovalStatus, RiskLevel
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import (
    ApprovalAlreadyResolved,
    ApprovalPayloadMismatch,
    SourceProcessingFailed,
    SourceTypeNotSupported,
    TaskCreationFailed,
    TaskProposalNeedsConfirmation,
    TaskProposalNotFound,
)
from app.models.entities import (
    ApprovalRequest,
    ProjectSource,
    ProjectTask,
    ProposedAction,
    WorkflowDefinition,
    WorkflowRun,
)
from app.repositories.relay import RelayRepository
from app.runtime.client import ExecutionRequest, ExecutionStatus, RuntimeClient
from app.runtime.sync import poll_until_terminal
from app.schemas.domain import ApprovalRead
from app.services.approvals import ApprovalService
from app.services.audit import record
from app.services.workflows import WorkflowService
from app.sources.analysis import SourceAnalysisService
from app.sources.dedupe import DuplicateCandidate, find_possible_duplicate
from app.sources.schemas import (
    SourceCaptureInput,
    SourceRead,
    TaskExecutionResult,
    TaskProposalEdit,
    TaskProposalRead,
    TaskRead,
)

CREATE_TASK_OPERATION = "create_relay_task"
ALLOWED_TYPES = {
    "SCHOOL": {"ASSIGNMENT_BRIEF", "COURSE_OUTLINE", "STUDY_GOAL"},
    "WORK": {"MEETING_TRANSCRIPT", "DOCUMENT_BRIEF"},
    "PERSONAL": {"PERSONAL_GOAL", "NOTES_CHECKLIST"},
}


class SourceCaptureService:
    def __init__(self, repo: RelayRepository, analyzer: SourceAnalysisService):
        self.repo, self.session, self.analyzer = repo, repo.session, analyzer

    async def capture(
        self, project_id: UUID, owner: UUID, user_name: str, data: SourceCaptureInput
    ) -> SourceRead:
        project = await self.repo.project(project_id, owner)
        if data.source_type not in ALLOWED_TYPES[project.space]:
            raise SourceTypeNotSupported()
        source = ProjectSource(
            user_id=owner,
            project_workspace_id=project.id,
            source_type=data.source_type,
            title=data.title,
            original_filename=data.original_filename,
            content=data.content,
            status="PROCESSING",
        )
        self.session.add(source)
        await self.session.flush()
        try:
            batch = await self.analyzer.generate(data, current_user=user_name)
            definition = await self.session.scalar(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.key == "source_to_tasks",
                    WorkflowDefinition.version == 1,
                    WorkflowDefinition.enabled.is_(True),
                )
            )
            if definition is None:
                raise SourceProcessingFailed()
            workflow = WorkflowService(self.repo)
            candidates = await self._duplicate_candidates(project.id, owner)
            for proposal in batch.proposals:
                match = find_possible_duplicate(proposal.title, proposal.description, candidates)
                run = WorkflowRun(
                    user_id=owner,
                    workflow_definition_id=definition.id,
                    project_workspace_id=project.id,
                    status=S.DRAFT,
                    input_payload={"source_id": str(source.id)},
                )
                self.session.add(run)
                await self.session.flush()
                await workflow.apply_transition(run, S.ANALYZING, owner)
                await workflow.apply_transition(run, S.PLAN_READY, owner)
                payload = TaskProposalEdit(
                    **proposal.model_dump(),
                    source_id=source.id,
                    project_id=project.id,
                    possible_duplicate=match is not None,
                    duplicate_of_title=match.title if match else None,
                ).model_dump(mode="json")
                action = ProposedAction(
                    workflow_run_id=run.id,
                    provider=ActionProvider.RELAY,
                    action_type=CREATE_TASK_OPERATION,
                    payload=payload,
                    risk_level=RiskLevel.LOW,
                    status=ActionStatus.PROPOSED,
                )
                self.session.add(action)
                await self.session.flush()
                approval = ApprovalRequest(
                    workflow_run_id=run.id,
                    proposed_action_id=action.id,
                    status=ApprovalStatus.PENDING,
                    original_payload=deepcopy(payload),
                )
                self.session.add(approval)
                await self.session.flush()
                record(
                    self.session,
                    owner,
                    "TASK_PROPOSAL_CREATED",
                    run.id,
                    {
                        "source_id": str(source.id),
                        "approval_id": str(approval.id),
                        **({"possible_duplicate_of": match.reference} if match else {}),
                    },
                )
                await workflow.apply_transition(run, S.AWAITING_APPROVAL, owner)
                # Later proposals in this same batch should also be checked
                # against earlier ones from this batch, not just prior state.
                candidates.append(
                    DuplicateCandidate(
                        f"proposal:{approval.id}", proposal.title, proposal.description
                    )
                )
            source.status = "READY"
            record(
                self.session,
                owner,
                "SOURCE_PROCESSED",
                metadata={"source_id": str(source.id), "proposal_count": len(batch.proposals)},
            )
            await self.session.commit()
        except Exception as error:
            await self.session.rollback()
            failed = ProjectSource(
                id=source.id,
                user_id=owner,
                project_workspace_id=project.id,
                source_type=data.source_type,
                title=data.title,
                original_filename=data.original_filename,
                content=data.content,
                status="FAILED",
                error_message="Relay couldn't process this source.",
            )
            self.session.add(failed)
            await self.session.commit()
            if isinstance(error, (SourceTypeNotSupported, SourceProcessingFailed)):
                raise
            raise SourceProcessingFailed() from error
        return SourceRead.model_validate(source)

    async def list_sources(self, project_id: UUID, owner: UUID) -> list[SourceRead]:
        return [
            SourceRead.model_validate(item) for item in await self.repo.sources(project_id, owner)
        ]

    async def _duplicate_candidates(
        self, project_id: UUID, owner: UUID
    ) -> list[DuplicateCandidate]:
        """Existing tasks and pending proposals in this project, for dedupe checks.

        Accepted/executed proposals are covered via `repo.tasks` (accepting a
        proposal creates a ProjectTask), so this is the full set of
        "already known" work items to compare a new proposal against.
        """
        candidates = [
            DuplicateCandidate(f"task:{task.id}", task.title, task.description)
            for task in await self.repo.tasks(project_id, owner)
        ]
        rows = (
            await self.session.execute(
                select(ApprovalRequest.id, ProposedAction.payload)
                .join(ProposedAction, ProposedAction.id == ApprovalRequest.proposed_action_id)
                .join(WorkflowRun, WorkflowRun.id == ApprovalRequest.workflow_run_id)
                .where(
                    WorkflowRun.user_id == owner,
                    WorkflowRun.project_workspace_id == project_id,
                    ApprovalRequest.status == ApprovalStatus.PENDING,
                    ProposedAction.action_type == CREATE_TASK_OPERATION,
                )
            )
        ).all()
        for approval_id, payload in rows:
            data = TaskProposalEdit.model_validate(payload)
            candidates.append(
                DuplicateCandidate(f"proposal:{approval_id}", data.title, data.description)
            )
        return candidates


class TaskProposalService:
    def __init__(self, repo: RelayRepository):
        self.repo, self.session = repo, repo.session

    async def list(self, owner: UUID) -> list[TaskProposalRead]:
        rows = (
            await self.session.execute(
                select(ApprovalRequest, ProposedAction, WorkflowRun)
                .join(ProposedAction, ProposedAction.id == ApprovalRequest.proposed_action_id)
                .join(WorkflowRun, WorkflowRun.id == ApprovalRequest.workflow_run_id)
                .where(
                    WorkflowRun.user_id == owner,
                    ProposedAction.action_type == CREATE_TASK_OPERATION,
                )
                .order_by(ApprovalRequest.requested_at.desc())
            )
        ).all()
        result: list[TaskProposalRead] = []
        for approval, action, run in rows:
            payload = TaskProposalEdit.model_validate(action.payload)
            project = await self.repo.project(payload.project_id, owner)
            source = await self.repo.source(payload.source_id, owner)
            result.append(
                TaskProposalRead(
                    approval_id=approval.id,
                    run_id=run.id,
                    action_id=action.id,
                    status=approval.status.value,
                    project_id=project.id,
                    project_name=project.name,
                    project_space=project.space,
                    source_id=source.id,
                    source_title=source.title,
                    source_type=source.source_type,
                    proposal=payload,
                    requested_at=approval.requested_at,
                )
            )
        return result

    async def edit(
        self, approval_id: UUID, owner: UUID, data: TaskProposalEdit
    ) -> TaskProposalRead:
        approval, action, run = await self._owned(approval_id, owner)
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyResolved()
        current = TaskProposalEdit.model_validate(action.payload)
        if data.source_id != current.source_id or data.project_id != current.project_id:
            raise ApprovalPayloadMismatch()
        await self.repo.project(data.project_id, owner)
        await self.repo.source(data.source_id, owner)
        payload = data.model_dump(mode="json")
        action.payload = deepcopy(payload)
        action.status = ActionStatus.EDITED
        approval.original_payload = deepcopy(payload)
        record(
            self.session,
            owner,
            "TASK_PROPOSAL_EDITED",
            run.id,
            {"approval_id": str(approval.id)},
        )
        await self.session.commit()
        items = await self.list(owner)
        return next(item for item in items if item.approval_id == approval_id)

    async def reject(self, approval_id: UUID, owner: UUID) -> ApprovalRead:
        await self._owned(approval_id, owner)
        return await ApprovalService(self.repo).resolve(approval_id, owner, None, approve=False)

    async def accept(
        self,
        approval_id: UUID,
        owner: UUID,
        data: TaskProposalEdit,
        runtime: RuntimeClient,
    ) -> TaskExecutionResult:
        if data.needs_confirmation:
            raise TaskProposalNeedsConfirmation()
        edited = await self.edit(approval_id, owner, data)
        await ApprovalService(self.repo).resolve(
            approval_id,
            owner,
            edited.proposal.model_dump(mode="json"),
            approve=True,
        )
        return await TaskExecutionService(self.repo, runtime).execute(edited.run_id, owner)

    async def _owned(
        self, approval_id: UUID, owner: UUID
    ) -> tuple[ApprovalRequest, ProposedAction, WorkflowRun]:
        approval = await self.repo.approval(approval_id, owner)
        action = await self.session.get(ProposedAction, approval.proposed_action_id)
        run = await self.repo.run(approval.workflow_run_id, owner)
        if action is None or action.action_type != CREATE_TASK_OPERATION:
            raise TaskProposalNotFound()
        return approval, action, run


class TaskExecutionService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo, self.session, self.runtime = repo, repo.session, runtime

    async def execute(self, run_id: UUID, owner: UUID) -> TaskExecutionResult:
        run = await self.repo.run(run_id, owner, lock=True)
        actions = await self.repo.actions(run.id)
        approvals = await self.repo.run_approvals(run.id)
        if len(actions) != 1 or len(approvals) != 1:
            raise TaskCreationFailed()
        action, approval = actions[0], approvals[0]
        existing = await self.session.scalar(
            select(ProjectTask).where(ProjectTask.proposed_action_id == action.id)
        )
        if existing:
            return TaskExecutionResult(task_id=existing.id, duplicate=True)
        if (
            run.status != S.APPROVED
            or approval.status != ApprovalStatus.APPROVED
            or approval.approved_payload is None
        ):
            raise TaskCreationFailed()
        workflow = WorkflowService(self.repo)
        await workflow.apply_transition(run, S.QUEUED, owner)
        action.status = ActionStatus.QUEUED
        await self.session.commit()
        run = await self.repo.run(run_id, owner, lock=True)
        await workflow.apply_transition(run, S.EXECUTING, owner)
        action.status = ActionStatus.EXECUTING
        payload = TaskProposalEdit.model_validate(approval.approved_payload)
        key = f"source-task:{action.id}"
        snapshot = await self.runtime.submit_execution(
            ExecutionRequest(
                workflow_run_id=run.id,
                proposed_action_id=action.id,
                action_type=CREATE_TASK_OPERATION,
                approved_payload=cast(dict[str, JsonValue], approval.approved_payload),
                idempotency_key=key,
                correlation_id=key,
            )
        )
        snapshot = await poll_until_terminal(
            self.runtime,
            snapshot,
            max_attempts=get_settings().agent_runtime_poll_attempts,
            interval_seconds=get_settings().agent_runtime_poll_interval_seconds,
        )
        run.runtime_execution_id = snapshot.execution_id
        run.result_payload = {"execution": snapshot.model_dump(mode="json")}
        if snapshot.status != ExecutionStatus.SUCCEEDED:
            action.status = ActionStatus.FAILED
            run.error_code = snapshot.error_code or "TASK_CREATION_FAILED"
            run.error_message = "Relay couldn't create the selected task. Please retry."
            await workflow.apply_transition(run, S.FAILED, owner)
            await self.session.commit()
            raise TaskCreationFailed()
        project = await self.repo.project(payload.project_id, owner)
        source = await self.repo.source(payload.source_id, owner)
        if source.project_workspace_id != project.id:
            raise ApprovalPayloadMismatch()
        task = ProjectTask(
            user_id=owner,
            project_workspace_id=project.id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            estimate_minutes=payload.estimate_minutes,
            priority=payload.priority,
            status="TODO",
            source_id=source.id,
            source_reference=payload.source_reference,
            proposed_action_id=action.id,
        )
        self.session.add(task)
        await self.session.flush()
        action.status = ActionStatus.COMPLETED
        run.result_payload = {**(run.result_payload or {}), "task_id": str(task.id)}
        await workflow.apply_transition(run, S.COMPLETED, owner)
        record(
            self.session,
            owner,
            "TASK_CREATED_FROM_SOURCE",
            run.id,
            {"task_id": str(task.id), "source_id": str(source.id)},
        )
        await self.session.commit()
        return TaskExecutionResult(task_id=task.id)


async def task_reads(repo: RelayRepository, project_id: UUID, owner: UUID) -> list[TaskRead]:
    result: list[TaskRead] = []
    for task in await repo.tasks(project_id, owner):
        source = await repo.source(task.source_id, owner) if task.source_id else None
        result.append(
            TaskRead(
                id=task.id,
                project_id=task.project_workspace_id,
                title=task.title,
                description=task.description,
                due_date=task.due_date,
                estimate_minutes=task.estimate_minutes,
                priority=task.priority,
                status=task.status,
                source_id=task.source_id,
                source_title=source.title if source else None,
                source_type=source.source_type if source else None,
                source_reference=task.source_reference,
                created_at=task.created_at,
            )
        )
    return result
