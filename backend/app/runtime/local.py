from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion import CreateNotionStudyPageAction, NotionConnector
from app.domain.errors import ApprovalPayloadMismatch, DomainError, UnauthorizedResourceAccess
from app.models.entities import LocalExecution, now
from app.runtime.client import ExecutionRequest, ExecutionSnapshot, ExecutionStatus
from app.workflows.lecture_notes.actions import OPERATION


class LocalRuntimeClient:
    """Synchronous local execution. Caller owns transaction; no background queue or retries."""

    def __init__(self, session: AsyncSession, connector: NotionConnector):
        self.session, self.connector = session, connector

    async def submit_execution(self, request: ExecutionRequest) -> ExecutionSnapshot:
        existing = await self.session.scalar(
            select(LocalExecution).where(
                LocalExecution.idempotency_key == request.idempotency_key,
            )
        )
        if existing:
            if (
                existing.request_payload != request.payload
                or existing.operation != request.operation
            ):
                raise ApprovalPayloadMismatch()
            return ExecutionSnapshot.model_validate(existing.snapshot)
        instant = now()
        snapshot = ExecutionSnapshot(
            execution_id=uuid4(),
            status=ExecutionStatus.RUNNING,
            submitted_at=instant,
            started_at=instant,
        )
        try:
            if request.operation != OPERATION:
                raise ValueError("Unsupported local operation")
            action = CreateNotionStudyPageAction.model_validate(request.payload)
            result = await self.connector.create_study_page(action, request.idempotency_key)
            snapshot.result = result.model_dump(mode="json")
            snapshot.status = ExecutionStatus.SUCCEEDED
        except Exception as error:
            snapshot.status = ExecutionStatus.FAILED
            snapshot.error_code = (
                error.code if isinstance(error, DomainError) else "EXECUTION_FAILED"
            )
        snapshot.completed_at = now()
        self.session.add(
            LocalExecution(
                id=snapshot.execution_id,
                idempotency_key=request.idempotency_key,
                operation=request.operation,
                request_payload=request.payload,
                snapshot=snapshot.model_dump(mode="json"),
            )
        )
        await self.session.flush()
        return snapshot

    async def get_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        execution = await self.session.get(LocalExecution, execution_id)
        if execution is None:
            raise UnauthorizedResourceAccess()
        return ExecutionSnapshot.model_validate(execution.snapshot)

    async def cancel_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        # Local submissions finish inline, so cancellation cannot interrupt a submitted call.
        return await self.get_execution(execution_id)
