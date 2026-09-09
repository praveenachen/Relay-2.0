from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion import (
    CreateNotionStudyPageAction,
    ExternalArtifactResult,
    NotionApiClient,
    NotionAuthorizationFailed,
    NotionConnector,
    NotionNotConnected,
    RealNotionConnector,
)
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import ApprovalPayloadMismatch, DomainError, UnauthorizedResourceAccess
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount, LocalExecution, now
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


class DatabaseNotionConnector:
    def __init__(
        self,
        session: AsyncSession,
        store: CredentialStore,
        *,
        api_base_url: str,
        timeout: int,
    ):
        self.session, self.store = session, store
        self.api_base_url, self.timeout = api_base_url, timeout

    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        if not action.connection_id:
            raise NotionNotConnected()
        connection = await self.session.get(ConnectedAccount, UUID(action.connection_id))
        if (
            connection is None
            or connection.provider != Provider.NOTION
            or connection.status != ConnectionStatus.CONNECTED
            or connection.access_token_encrypted is None
        ):
            raise NotionNotConnected()
        token = self.store.decrypt(connection.access_token_encrypted)
        try:
            return await RealNotionConnector(
                NotionApiClient(token, base_url=self.api_base_url, timeout=self.timeout)
            ).create_study_page(action, idempotency_key)
        except NotionAuthorizationFailed:
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            raise
