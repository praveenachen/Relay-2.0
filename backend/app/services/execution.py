from uuid import UUID

from sqlalchemy import select

from app.connectors.notion import ExternalArtifactResult
from app.core.config import get_settings
from app.domain.enums import ActionProvider, ActionStatus, ApprovalStatus
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
from app.workflows.lecture_notes.actions import OPERATION
from app.workflows.lecture_notes.errors import LearnWorkflowInvalidState


class ExecutionService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo, self.session, self.runtime = repo, repo.session, runtime

    async def execute(self, run_id: UUID, owner: UUID) -> RunRead:
        run = await self.repo.run(run_id, owner, lock=True)
        if run.status == S.COMPLETED:
            return RunRead.model_validate(run)
        if run.status != S.APPROVED:
            raise LearnWorkflowInvalidState()
        actions = await self.repo.actions(run_id)
        approvals = await self.repo.run_approvals(run_id)
        if len(actions) != 1 or len(approvals) != 1 or actions[0].action_type != OPERATION:
            raise ApprovalRequired()
        action, approval = actions[0], approvals[0]
        if approval.status != ApprovalStatus.APPROVED or approval.approved_payload is None:
            raise ApprovalRequired()
        workflow = WorkflowService(self.repo)
        key = f"learn:{run.id}:{approval.id}"
        existing = await self.session.scalar(
            select(ExternalArtifact).where(ExternalArtifact.idempotency_key == key)
        )
        if existing is not None:
            run.result_payload = {
                "artifact_id": str(existing.id),
                "artifact": {
                    "external_id": existing.external_id,
                    "external_url": existing.external_url,
                },
            }
            action.status = ActionStatus.COMPLETED
            await workflow.apply_transition(run, S.COMPLETED, owner)
            await self.session.commit()
            return RunRead.model_validate(run)
        await workflow.apply_transition(run, S.QUEUED, owner)
        action.status = ActionStatus.QUEUED
        record(self.session, owner, "EXECUTION_SUBMITTED", run.id, {"action_id": str(action.id)})
        await self.session.commit()
        run = await self.repo.run(run_id, owner, lock=True)
        await workflow.apply_transition(run, S.EXECUTING, owner)
        action.status = ActionStatus.EXECUTING
        record(
            self.session, owner, "EXTERNAL_EXECUTION_STARTED", run.id, {"action_id": str(action.id)}
        )
        record(self.session, owner, "NOTION_PAGE_CREATE_STARTED", run.id)
        # Inline local side effects and their records commit together. Runtime never reads a
        # mutable proposal: only the approved snapshot crosses this boundary.
        correlation_id = f"learn:{run.id}:{action.id}"
        snapshot = await self.runtime.submit_execution(
            ExecutionRequest(
                workflow_run_id=run.id,
                proposed_action_id=action.id,
                action_type=action.action_type,
                approved_payload=approval.approved_payload,
                idempotency_key=key,
                correlation_id=correlation_id,
            )
        )
        snapshot = await poll_until_terminal(
            self.runtime,
            snapshot,
            max_attempts=get_settings().agent_runtime_poll_attempts,
            interval_seconds=get_settings().agent_runtime_poll_interval_seconds,
        )
        run.runtime_execution_id = snapshot.execution_id
        run.result_payload = {
            "execution": snapshot.model_dump(mode="json"),
            "correlation_id": correlation_id,
        }
        if not runtime_status_is_terminal(snapshot.status):
            action.status = (
                ActionStatus.QUEUED
                if snapshot.status == ExecutionStatus.QUEUED
                else ActionStatus.EXECUTING
            )
            await workflow.apply_transition(
                run, workflow_status_for_runtime(snapshot.status), owner
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
            await self.session.commit()
            return RunRead.model_validate(run)
        if snapshot.status == ExecutionStatus.CANCELLED:
            action.status = ActionStatus.FAILED
            await workflow.apply_transition(run, S.CANCELLED, owner)
            await self.session.commit()
            return RunRead.model_validate(run)
        if snapshot.status == ExecutionStatus.SUCCEEDED and snapshot.result is not None:
            result = ExternalArtifactResult.model_validate(snapshot.result)
            connection_id = approval.approved_payload.get("connection_id")
            artifact = ExternalArtifact(
                workflow_run_id=run.id,
                proposed_action_id=action.id,
                connected_account_id=UUID(connection_id) if connection_id else None,
                provider=ActionProvider.NOTION,
                artifact_type="notion_study_page"
                if not result.simulated
                else "mock_notion_study_page",
                external_id=result.external_id,
                external_url=result.external_url,
                idempotency_key=key,
            )
            self.session.add(artifact)
            await self.session.flush()
            run.result_payload = {**run.result_payload, "artifact_id": str(artifact.id)}
            action.status = ActionStatus.COMPLETED
            record(
                self.session,
                owner,
                "EXTERNAL_ACTION_COMPLETED",
                run.id,
                {
                    "artifact_id": str(artifact.id),
                    "simulated": result.simulated,
                },
            )
            record(
                self.session,
                owner,
                "NOTION_PAGE_CREATED",
                run.id,
                {
                    "artifact_id": str(artifact.id),
                    "destination_id": result.destination_id,
                },
            )
            record(
                self.session,
                owner,
                "EXTERNAL_ARTIFACT_RECORDED",
                run.id,
                {"artifact_id": str(artifact.id)},
            )
            await workflow.apply_transition(run, S.COMPLETED, owner)
            record(self.session, owner, "WORKFLOW_COMPLETED", run.id)
        else:
            action.status = ActionStatus.FAILED
            run.error_code = snapshot.error_code or "EXECUTION_FAILED"
            run.error_message = (
                "Relay could not publish the approved notes. Check the Notion connection "
                "and destination."
            )
            record(
                self.session,
                owner,
                "NOTION_PAGE_CREATE_FAILED",
                run.id,
                {
                    "error_code": run.error_code,
                },
            )
            record(
                self.session,
                owner,
                "EXTERNAL_ACTION_FAILED",
                run.id,
                {
                    "error_code": run.error_code,
                },
            )
            await workflow.apply_transition(run, S.FAILED, owner)
        await self.session.commit()
        return RunRead.model_validate(run)
