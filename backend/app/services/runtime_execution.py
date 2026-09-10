from uuid import UUID

from app.domain.enums import ActionStatus
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import InvalidWorkflowTransition
from app.repositories.relay import RelayRepository
from app.runtime.client import ExecutionStatus, RuntimeClient
from app.runtime.state import workflow_status_for_runtime
from app.schemas.domain import RunRead
from app.services.audit import record
from app.services.workflows import WorkflowService


class RuntimeExecutionService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo = repo
        self.session = repo.session
        self.runtime = runtime

    async def cancel(self, run_id: UUID, owner: UUID) -> RunRead:
        run = await self.repo.run(run_id, owner, lock=True)
        workflow = WorkflowService(self.repo)
        if run.status in {S.COMPLETED, S.PARTIALLY_COMPLETED, S.FAILED, S.REJECTED, S.CANCELLED}:
            return RunRead.model_validate(run)
        record(self.session, owner, "RUNTIME_CANCEL_REQUESTED", run.id)
        if run.runtime_execution_id is None:
            await workflow.apply_transition(run, S.CANCELLED, owner)
            await self.session.commit()
            return RunRead.model_validate(run)
        snapshot = await self.runtime.cancel_execution(run.runtime_execution_id)
        run.result_payload = {
            **(run.result_payload or {}),
            "execution": snapshot.model_dump(mode="json"),
        }
        target = workflow_status_for_runtime(snapshot.status)
        if target != S.CANCELLED and snapshot.status != ExecutionStatus.CANCELLED:
            raise InvalidWorkflowTransition()
        actions = await self.repo.actions(run.id)
        for action in actions:
            if action.status in {ActionStatus.QUEUED, ActionStatus.EXECUTING}:
                action.status = ActionStatus.FAILED
        record(
            self.session,
            owner,
            "RUNTIME_CANCELLED",
            run.id,
            {"runtime_execution_id": str(snapshot.execution_id), "status": snapshot.status.value},
        )
        await workflow.apply_transition(run, S.CANCELLED, owner)
        await self.session.commit()
        return RunRead.model_validate(run)
