import json
from copy import deepcopy
from typing import Any
from uuid import UUID

from app.domain.enums import ActionStatus, ApprovalStatus, WorkflowStatus
from app.domain.errors import (
    ApprovalAlreadyResolved,
    ApprovalPayloadMismatch,
    InvalidWorkflowTransition,
)
from app.models.entities import ProposedAction, now
from app.repositories.relay import RelayRepository
from app.schemas.domain import ApprovalRead
from app.services.audit import record
from app.services.workflows import WorkflowService


def exact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ApprovalService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository
        self.session = repository.session

    async def resolve(
        self, approval_id: UUID, owner: UUID, payload: dict[str, Any] | None, *, approve: bool
    ) -> ApprovalRead:
        approval = await self.repo.approval(approval_id, owner)
        # Every resolution locks the parent first, serializing decisions for the entire plan.
        run = await self.repo.run(approval.workflow_run_id, owner, lock=True)
        await self.session.refresh(approval)
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyResolved()
        if run.status != WorkflowStatus.AWAITING_APPROVAL:
            raise InvalidWorkflowTransition()
        action = await self.session.get(ProposedAction, approval.proposed_action_id)
        if action is None or action.status not in {ActionStatus.PROPOSED, ActionStatus.EDITED}:
            raise ApprovalPayloadMismatch()
        if approve:
            if (
                payload is None
                or exact_json(payload) != exact_json(approval.original_payload)
                or (exact_json(action.payload) != exact_json(approval.original_payload))
            ):
                raise ApprovalPayloadMismatch()
            approval.approved_payload = deepcopy(payload)
            approval.status = ApprovalStatus.APPROVED
            action.status = ActionStatus.APPROVED
        else:
            approval.status = ApprovalStatus.REJECTED
            action.status = ActionStatus.REJECTED
        approval.resolved_at = now()
        approval.resolved_by = owner
        record(
            self.session,
            owner,
            "ACTION_APPROVED" if approve else "ACTION_REJECTED",
            run.id,
            {"approval_id": str(approval.id), "action_id": str(action.id)},
        )
        await self.session.flush()
        pending = await self.repo.run_approvals(run.id)
        workflow = WorkflowService(self.repo)
        if not approve:
            for other in pending:
                if other.status == ApprovalStatus.PENDING:
                    other.status = ApprovalStatus.EXPIRED
                    other.resolved_at = now()
                    record(
                        self.session,
                        owner,
                        "APPROVAL_EXPIRED",
                        run.id,
                        {"approval_id": str(other.id), "reason": "PLAN_REJECTED"},
                    )
            await workflow.apply_transition(run, WorkflowStatus.REJECTED, owner)
        elif all(item.status == ApprovalStatus.APPROVED for item in pending):
            await workflow.apply_transition(run, WorkflowStatus.APPROVED, owner)
        await self.session.commit()
        return ApprovalRead.model_validate(approval)
