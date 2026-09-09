from copy import deepcopy
from uuid import UUID

from app.domain.enums import ActionStatus, ApprovalStatus
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import (
    ApprovalRequired,
    InvalidWorkflowTransition,
    WorkflowDefinitionDisabled,
    WorkflowNotFound,
)
from app.domain.workflows import transition
from app.models.entities import ApprovalRequest, WorkflowDefinition, WorkflowRun
from app.repositories.relay import RelayRepository
from app.schemas.domain import RunInput, RunRead
from app.services.audit import record


class WorkflowService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository
        self.session = repository.session

    async def create(self, owner: UUID, data: RunInput) -> RunRead:
        definition = await self.session.get(WorkflowDefinition, data.workflow_definition_id)
        if definition is None:
            raise WorkflowNotFound()
        if not definition.enabled:
            raise WorkflowDefinitionDisabled()
        run = WorkflowRun(
            user_id=owner,
            workflow_definition_id=definition.id,
            status=S.DRAFT,
            input_payload=deepcopy(data.input_payload),
        )
        self.session.add(run)
        await self.session.flush()
        record(
            self.session, owner, "WORKFLOW_CREATED", run.id, {"definition_id": str(definition.id)}
        )
        await self.session.commit()
        return RunRead.model_validate(run)

    async def apply_transition(self, run: WorkflowRun, target: S, owner: UUID) -> None:
        """Transaction-internal operation; the caller must lock the run and commit."""
        if run.user_id != owner:
            raise WorkflowNotFound()
        change = transition(run.status, target, run.started_at)
        if target in {S.AWAITING_APPROVAL, S.APPROVED, S.QUEUED}:
            actions = await self.repo.actions(run.id)
            approvals = await self.repo.run_approvals(run.id)
            if not actions or {a.id for a in actions} != {a.proposed_action_id for a in approvals}:
                raise ApprovalRequired()
            if target in {S.APPROVED, S.QUEUED} and any(
                approval.status != ApprovalStatus.APPROVED for approval in approvals
            ):
                raise ApprovalRequired()
            if target == S.AWAITING_APPROVAL and any(
                approval.status != ApprovalStatus.PENDING for approval in approvals
            ):
                raise ApprovalRequired()
        run.status = change.current
        run.updated_at = change.updated_at
        run.started_at = change.started_at
        run.completed_at = change.completed_at
        record(
            self.session,
            owner,
            "WORKFLOW_STATE_CHANGED",
            run.id,
            {"from": change.previous.value, "to": change.current.value},
        )
        await self.session.flush()

    async def transition_workflow(self, run_id: UUID, target: S, owner: UUID) -> RunRead:
        run = await self.repo.run(run_id, owner, lock=True)
        await self.apply_transition(run, target, owner)
        await self.session.commit()
        return RunRead.model_validate(run)

    async def request_approvals(self, run_id: UUID, owner: UUID) -> None:
        """Internal planning port; no public proposal-generation endpoint exists."""
        run = await self.repo.run(run_id, owner, lock=True)
        if run.status != S.PLAN_READY:
            raise InvalidWorkflowTransition()
        actions = await self.repo.actions(run.id)
        if not actions or await self.repo.run_approvals(run.id):
            raise ApprovalRequired()
        for action in actions:
            if action.status not in {ActionStatus.PROPOSED, ActionStatus.EDITED}:
                raise ApprovalRequired()
            approval = ApprovalRequest(
                workflow_run_id=run.id,
                proposed_action_id=action.id,
                original_payload=deepcopy(action.payload),
                status=ApprovalStatus.PENDING,
            )
            self.session.add(approval)
            await self.session.flush()
            record(
                self.session,
                owner,
                "APPROVAL_REQUESTED",
                run.id,
                {"approval_id": str(approval.id), "action_id": str(action.id)},
            )
        await self.apply_transition(run, S.AWAITING_APPROVAL, owner)
        await self.session.commit()
