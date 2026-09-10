from uuid import UUID

from sqlalchemy import select

from app.connectors.google.schemas import CalendarEventResult
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
from app.workflows.study_plan.actions import OPERATION, CreateCalendarStudyPlanAction
from app.workflows.study_plan.errors import PlanWorkflowInvalidState


class StudyPlanExecutionService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo = repo
        self.session = repo.session
        self.runtime = runtime

    async def execute(self, run_id: UUID, owner: UUID) -> RunRead:
        run = await self.repo.run(run_id, owner, lock=True)
        if run.status == S.COMPLETED:
            return RunRead.model_validate(run)
        if run.status != S.APPROVED:
            raise PlanWorkflowInvalidState()
        actions = await self.repo.actions(run_id)
        approvals = await self.repo.run_approvals(run_id)
        if len(actions) != 1 or len(approvals) != 1 or actions[0].action_type != OPERATION:
            raise ApprovalRequired()
        action, approval = actions[0], approvals[0]
        if approval.status != ApprovalStatus.APPROVED or approval.approved_payload is None:
            raise ApprovalRequired()
        workflow = WorkflowService(self.repo)
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
        idempotency_key = f"plan:{run.id}:{approval.id}"
        correlation_id = f"plan:{run.id}:{action.id}"
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
        plan = CreateCalendarStudyPlanAction.model_validate(approval.approved_payload)
        artifact_ids: list[str] = []
        created_count = 0
        failed_count = 0
        if snapshot.result is not None:
            created_items = snapshot.result.get("created", [])
            for item in created_items if isinstance(created_items, list) else []:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                event = CalendarEventResult.model_validate(item.get("event"))
                idempotency_key = f"plan:{run.id}:{approval.id}:{index}"
                existing = await self.session.scalar(
                    select(ExternalArtifact).where(
                        ExternalArtifact.idempotency_key == idempotency_key
                    )
                )
                if existing is None:
                    event_action = (
                        plan.events[index]
                        if isinstance(index, int) and index < len(plan.events)
                        else None
                    )
                    connection_id = (
                        event_action.connection_id if event_action else None
                    ) or approval.approved_payload.get("connection_id")
                    artifact = ExternalArtifact(
                        workflow_run_id=run.id,
                        proposed_action_id=action.id,
                        connected_account_id=UUID(connection_id) if connection_id else None,
                        provider=ActionProvider.GOOGLE_CALENDAR,
                        artifact_type="calendar_study_block",
                        external_id=event.external_id,
                        external_url=event.external_url,
                        idempotency_key=idempotency_key,
                    )
                    self.session.add(artifact)
                    await self.session.flush()
                    artifact_ids.append(str(artifact.id))
                    record(
                        self.session,
                        owner,
                        "CALENDAR_EVENT_CREATED",
                        run.id,
                        {"artifact_id": str(artifact.id)},
                    )
                else:
                    artifact_ids.append(str(existing.id))
                created_count += 1
            failed_items = snapshot.result.get("failed", [])
            failed_count = len(failed_items) if isinstance(failed_items, list) else 0
        run.result_payload = {
            **run.result_payload,
            "artifact_ids": artifact_ids,
            "created_count": created_count,
            "failed_count": failed_count,
            "approved_count": len(plan.events),
        }
        if artifact_ids:
            record(
                self.session,
                owner,
                "EXTERNAL_ARTIFACT_RECORDED",
                run.id,
                {"count": len(artifact_ids)},
            )
        if snapshot.status == ExecutionStatus.SUCCEEDED:
            action.status = ActionStatus.COMPLETED
            await workflow.apply_transition(run, S.COMPLETED, owner)
            record(self.session, owner, "WORKFLOW_COMPLETED", run.id)
        elif snapshot.status == ExecutionStatus.PARTIAL:
            action.status = ActionStatus.FAILED
            run.error_code = snapshot.error_code or "CALENDAR_EVENT_CREATE_FAILED"
            run.error_message = (
                f"Relay created {created_count} of {len(plan.events)} approved study blocks; "
                f"{failed_count} could not be created."
            )
            record(
                self.session,
                owner,
                "CALENDAR_EVENT_CREATE_FAILED",
                run.id,
                {"error_code": run.error_code, "created": created_count, "failed": failed_count},
            )
            await workflow.apply_transition(run, S.PARTIALLY_COMPLETED, owner)
        else:
            action.status = ActionStatus.FAILED
            run.error_code = snapshot.error_code or "CALENDAR_EVENT_CREATE_FAILED"
            run.error_message = "Relay could not create any of the approved study blocks."
            record(
                self.session,
                owner,
                "CALENDAR_EVENT_CREATE_FAILED",
                run.id,
                {"error_code": run.error_code},
            )
            await workflow.apply_transition(run, S.FAILED, owner)
        await self.session.commit()
        return RunRead.model_validate(run)
