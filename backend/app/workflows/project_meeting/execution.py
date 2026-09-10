from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.domain.enums import ActionStatus, ApprovalStatus
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import ApprovalRequired
from app.models.entities import ExternalArtifact
from app.repositories.relay import RelayRepository
from app.runtime.client import ExecutionRequest, ExecutionStatus, RuntimeClient
from app.runtime.state import runtime_status_is_terminal, workflow_status_for_runtime
from app.runtime.sync import poll_until_terminal
from app.schemas.domain import RunRead
from app.services.audit import record
from app.services.workflows import WorkflowService
from app.workflows.project_meeting.errors import CollaborateWorkflowInvalidState

# Artifact types, keyed by the action_type each ProposedAction carries.
_ARTIFACT_TYPES = {
    "create_notion_task": "notion_task",
    "create_github_issue": "github_issue",
    "request_github_pr_review": "github_review_request",
}


class CollaborateExecutionService:
    """A COLLABORATE run typically has several independent ProposedActions
    (some Notion, some GitHub) rather than one envelope action like PLAN's
    calendar blocks. Each is submitted to the RuntimeClient on its own, so
    one failing GitHub call cannot prevent the Notion tasks -- or the other
    GitHub calls -- from succeeding. See docs/architecture/collaborate-
    sequence.md."""

    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo = repo
        self.session = repo.session
        self.runtime = runtime

    async def execute(self, run_id: UUID, owner: UUID) -> RunRead:
        run = await self.repo.run(run_id, owner, lock=True)
        if run.status == S.COMPLETED:
            return RunRead.model_validate(run)
        if run.status != S.APPROVED:
            raise CollaborateWorkflowInvalidState()
        actions = await self.repo.actions(run_id)
        approvals = await self.repo.run_approvals(run_id)
        if not actions or len(actions) != len(approvals):
            raise ApprovalRequired()
        approval_by_action = {approval.proposed_action_id: approval for approval in approvals}
        if any(
            approval_by_action.get(action.id) is None
            or approval_by_action[action.id].status != ApprovalStatus.APPROVED
            or approval_by_action[action.id].approved_payload is None
            for action in actions
        ):
            raise ApprovalRequired()

        workflow = WorkflowService(self.repo)
        await workflow.apply_transition(run, S.QUEUED, owner)
        record(self.session, owner, "EXECUTION_SUBMITTED", run.id, {"action_count": len(actions)})
        await self.session.commit()
        run = await self.repo.run(run_id, owner, lock=True)
        await workflow.apply_transition(run, S.EXECUTING, owner)
        record(self.session, owner, "EXTERNAL_EXECUTION_STARTED", run.id)
        await self.session.commit()

        results: list[dict[str, Any]] = []
        for action in actions:
            approval = approval_by_action[action.id]
            action.status = ActionStatus.EXECUTING
            idempotency_key = f"collaborate:{run.id}:{action.id}"
            correlation_id = f"collaborate:{run.id}:{action.id}"
            snapshot = await self.runtime.submit_execution(
                ExecutionRequest(
                    workflow_run_id=run.id,
                    proposed_action_id=action.id,
                    action_type=action.action_type,
                    approved_payload=approval.approved_payload,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                )
            )
            snapshot = await poll_until_terminal(
                self.runtime,
                snapshot,
                max_attempts=get_settings().agent_runtime_poll_attempts,
                interval_seconds=get_settings().agent_runtime_poll_interval_seconds,
            )
            outcome: dict[str, Any] = {
                "action_id": str(action.id),
                "action_type": action.action_type,
                "status": snapshot.status.value,
                "runtime_execution_id": str(snapshot.execution_id),
                "correlation_id": correlation_id,
            }
            if not runtime_status_is_terminal(snapshot.status):
                action.status = (
                    ActionStatus.QUEUED
                    if snapshot.status == ExecutionStatus.QUEUED
                    else ActionStatus.EXECUTING
                )
                record(
                    self.session,
                    owner,
                    "RUNTIME_STATUS_SYNCED",
                    run.id,
                    {
                        "runtime_execution_id": str(snapshot.execution_id),
                        "status": snapshot.status.value,
                    },
                )
            elif snapshot.status == ExecutionStatus.CANCELLED:
                action.status = ActionStatus.FAILED
            elif snapshot.status == ExecutionStatus.SUCCEEDED and snapshot.result is not None:
                artifact = await self._record_artifact(run.id, action, snapshot.result)
                action.status = ActionStatus.COMPLETED
                outcome["artifact_id"] = str(artifact.id) if artifact else None
                outcome["external_url"] = artifact.external_url if artifact else None
                record(
                    self.session,
                    owner,
                    f"{action.provider.value}_ARTIFACT_CREATED",
                    run.id,
                    {"action_id": str(action.id)},
                )
            else:
                action.status = ActionStatus.FAILED
                outcome["error_code"] = snapshot.error_code or "EXECUTION_FAILED"
                record(
                    self.session,
                    owner,
                    f"{action.provider.value}_ACTION_FAILED",
                    run.id,
                    {"action_id": str(action.id), "error_code": outcome["error_code"]},
                )
            results.append(outcome)
        await self.session.commit()

        statuses = [ExecutionStatus(item["status"]) for item in results]
        succeeded = sum(1 for status in statuses if status == ExecutionStatus.SUCCEEDED)
        pending = any(
            status in {ExecutionStatus.QUEUED, ExecutionStatus.RUNNING} for status in statuses
        )
        run = await self.repo.run(run_id, owner, lock=True)
        run.result_payload = {
            "results": results,
            "succeeded_count": succeeded,
            "failed_count": len(results) - succeeded,
            "total_count": len(results),
        }
        if pending:
            await workflow.apply_transition(run, workflow_status_for_runtime(statuses[0]), owner)
            record(
                self.session,
                owner,
                "RUNTIME_STATUS_SYNCED",
                run.id,
                {
                    "pending_count": sum(
                        1 for status in statuses if not runtime_status_is_terminal(status)
                    )
                },
            )
        elif succeeded == len(results):
            await workflow.apply_transition(run, S.COMPLETED, owner)
            record(self.session, owner, "WORKFLOW_COMPLETED", run.id)
        elif succeeded > 0:
            run.error_code = "COLLABORATE_PARTIALLY_COMPLETED"
            run.error_message = f"Relay completed {succeeded} of {len(results)} approved actions."
            await workflow.apply_transition(run, S.PARTIALLY_COMPLETED, owner)
            record(
                self.session,
                owner,
                "PARTIAL_COMPLETION",
                run.id,
                {"succeeded": succeeded, "failed": len(results) - succeeded},
            )
        else:
            run.error_code = "COLLABORATE_EXECUTION_FAILED"
            run.error_message = "Relay could not complete any of the approved actions."
            await workflow.apply_transition(run, S.FAILED, owner)
        await self.session.commit()
        return RunRead.model_validate(run)

    async def _record_artifact(
        self, run_id: UUID, action: Any, result: dict[str, Any]
    ) -> ExternalArtifact | None:
        external_id = result.get("external_id")
        external_url = result.get("external_url")
        if not isinstance(external_id, str) or not isinstance(external_url, str):
            return None
        idempotency_key = f"collaborate:{run_id}:{action.id}"
        existing = await self.session.scalar(
            select(ExternalArtifact).where(ExternalArtifact.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        connection_id = action.payload.get("connection_id")
        artifact = ExternalArtifact(
            workflow_run_id=run_id,
            proposed_action_id=action.id,
            connected_account_id=UUID(connection_id) if connection_id else None,
            provider=action.provider,
            artifact_type=_ARTIFACT_TYPES.get(action.action_type, action.action_type),
            external_id=external_id,
            external_url=external_url,
            idempotency_key=idempotency_key,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact
