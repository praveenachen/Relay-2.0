from typing import Any
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.github.client import GitHubApiClient, GitHubConnector
from app.connectors.github.errors import GitHubAuthorizationFailed, GitHubNotConnected
from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubIssueResult,
    GitHubReviewRequestResult,
    RequestPullRequestReviewAction,
)
from app.connectors.google.calendar import GoogleCalendarApiClient, GoogleCalendarConnector
from app.connectors.google.errors import GoogleAuthorizationFailed, GoogleNotConnected
from app.connectors.google.schemas import CalendarEventResult, CreateCalendarStudyBlockAction
from app.connectors.notion import (
    CreateNotionStudyPageAction,
    CreateNotionTaskAction,
    ExternalArtifactResult,
    NotionApiClient,
    NotionAuthorizationFailed,
    NotionConnector,
    NotionNotConnected,
    NotionTaskResult,
    RealNotionConnector,
)
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import ApprovalPayloadMismatch, DomainError, UnauthorizedResourceAccess
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount, LocalExecution, now
from app.runtime.client import ExecutionRequest, ExecutionSnapshot, ExecutionStatus
from app.sources.schemas import TaskProposalEdit
from app.sources.service import CREATE_TASK_OPERATION
from app.workflows.lecture_notes.actions import OPERATION as LEARN_OPERATION
from app.workflows.project_meeting.actions import (
    CREATE_GITHUB_ISSUE_OPERATION,
    NOTION_TASK_OPERATION,
    REQUEST_GITHUB_PR_REVIEW_OPERATION,
)
from app.workflows.study_plan.actions import (
    OPERATION as PLAN_OPERATION,
)
from app.workflows.study_plan.actions import (
    CreateCalendarStudyPlanAction,
)


class LocalRuntimeClient:
    """Synchronous local execution. Caller owns transaction; no background queue or retries."""

    def __init__(
        self,
        session: AsyncSession,
        connector: NotionConnector | None = None,
        calendar_connector: Any | None = None,
        github_connector: Any | None = None,
    ):
        self.session = session
        self.connector = connector
        self.calendar_connector = calendar_connector
        self.github_connector = github_connector

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
            if request.operation == LEARN_OPERATION:
                if self.connector is None:
                    raise ValueError("Notion connector is not configured")
                action = CreateNotionStudyPageAction.model_validate(request.payload)
                notion_result = await self.connector.create_study_page(
                    action, request.idempotency_key
                )
                snapshot.result = notion_result.model_dump(mode="json")
                snapshot.status = ExecutionStatus.SUCCEEDED
            elif request.operation == PLAN_OPERATION:
                if self.calendar_connector is None:
                    raise ValueError("Google Calendar connector is not configured")
                plan = CreateCalendarStudyPlanAction.model_validate(request.payload)
                created: list[JsonValue] = []
                failed: list[JsonValue] = []
                first_error_code: str | None = None
                # Each study block is created independently: one failing
                # event must not discard calendar events already created for
                # other tasks, and must not block retrying only the rest.
                for index, event in enumerate(plan.events):
                    try:
                        calendar_result = await self.calendar_connector.create_study_block(
                            event, f"{request.idempotency_key}:{index}"
                        )
                        created.append(
                            {
                                "index": index,
                                "task_id": event.task_id,
                                "event": calendar_result.model_dump(mode="json"),
                            }
                        )
                    except Exception as event_error:
                        error_code = (
                            event_error.code
                            if isinstance(event_error, DomainError)
                            else "EXECUTION_FAILED"
                        )
                        first_error_code = first_error_code or error_code
                        failed.append(
                            {"index": index, "task_id": event.task_id, "error_code": error_code}
                        )
                snapshot.result = {"created": created, "failed": failed}
                if not failed:
                    snapshot.status = ExecutionStatus.SUCCEEDED
                elif created:
                    snapshot.status = ExecutionStatus.PARTIAL
                    snapshot.error_code = first_error_code
                else:
                    snapshot.status = ExecutionStatus.FAILED
                    snapshot.error_code = first_error_code
            elif request.operation == NOTION_TASK_OPERATION:
                if self.connector is None:
                    raise ValueError("Notion connector is not configured")
                task_action = CreateNotionTaskAction.model_validate(request.payload)
                task_result = await self.connector.create_task(task_action, request.idempotency_key)
                snapshot.result = task_result.model_dump(mode="json")
                snapshot.status = ExecutionStatus.SUCCEEDED
            elif request.operation == CREATE_GITHUB_ISSUE_OPERATION:
                if self.github_connector is None:
                    raise ValueError("GitHub connector is not configured")
                issue_action = CreateGitHubIssueAction.model_validate(request.payload)
                issue_result = await self.github_connector.create_issue(
                    issue_action, request.idempotency_key
                )
                snapshot.result = issue_result.model_dump(mode="json")
                snapshot.status = ExecutionStatus.SUCCEEDED
            elif request.operation == REQUEST_GITHUB_PR_REVIEW_OPERATION:
                if self.github_connector is None:
                    raise ValueError("GitHub connector is not configured")
                review_action = RequestPullRequestReviewAction.model_validate(request.payload)
                review_result = await self.github_connector.request_review(
                    review_action, request.idempotency_key
                )
                snapshot.result = review_result.model_dump(mode="json")
                snapshot.status = ExecutionStatus.SUCCEEDED
            elif request.operation == CREATE_TASK_OPERATION:
                task = TaskProposalEdit.model_validate(request.payload)
                snapshot.result = {
                    "accepted": True,
                    "project_id": str(task.project_id),
                    "source_id": str(task.source_id),
                }
                snapshot.status = ExecutionStatus.SUCCEEDED
            else:
                raise ValueError("Unsupported local operation")
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

    async def create_task(
        self,
        action: CreateNotionTaskAction,
        idempotency_key: str,
    ) -> NotionTaskResult:
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
            ).create_task(action, idempotency_key)
        except NotionAuthorizationFailed:
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            raise


class DatabaseGoogleCalendarConnector:
    def __init__(
        self,
        session: AsyncSession,
        store: CredentialStore,
        *,
        api_base_url: str,
        timeout: int,
    ):
        self.session = session
        self.store = store
        self.api_base_url = api_base_url
        self.timeout = timeout

    async def create_study_block(
        self,
        action: CreateCalendarStudyBlockAction,
        idempotency_key: str,
    ) -> CalendarEventResult:

        if not action.connection_id:
            raise GoogleNotConnected()
        connection = await self.session.get(ConnectedAccount, UUID(action.connection_id))
        if (
            connection is None
            or connection.provider != Provider.GOOGLE
            or connection.status != ConnectionStatus.CONNECTED
            or connection.access_token_encrypted is None
        ):
            raise GoogleNotConnected()
        token = self.store.decrypt(connection.access_token_encrypted)
        try:
            return await GoogleCalendarConnector(
                GoogleCalendarApiClient(token, base_url=self.api_base_url, timeout=self.timeout)
            ).create_study_block(action, idempotency_key)
        except GoogleAuthorizationFailed:
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            raise


class DatabaseGitHubConnector:
    def __init__(
        self,
        session: AsyncSession,
        store: CredentialStore,
        *,
        api_base_url: str,
        timeout: int,
    ):
        self.session = session
        self.store = store
        self.api_base_url = api_base_url
        self.timeout = timeout

    async def _connection(self, connection_id: str | None) -> ConnectedAccount:
        if not connection_id:
            raise GitHubNotConnected()
        connection = await self.session.get(ConnectedAccount, UUID(connection_id))
        if (
            connection is None
            or connection.provider != Provider.GITHUB
            or connection.status != ConnectionStatus.CONNECTED
            or connection.access_token_encrypted is None
        ):
            raise GitHubNotConnected()
        return connection

    async def create_issue(
        self,
        action: CreateGitHubIssueAction,
        idempotency_key: str,
    ) -> GitHubIssueResult:
        connection = await self._connection(action.connection_id)
        if connection.access_token_encrypted is None:
            raise GitHubNotConnected()
        token = self.store.decrypt(connection.access_token_encrypted)
        try:
            return await GitHubConnector(
                GitHubApiClient(token, base_url=self.api_base_url, timeout=self.timeout)
            ).create_issue(action, idempotency_key)
        except GitHubAuthorizationFailed:
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            raise

    async def request_review(
        self,
        action: RequestPullRequestReviewAction,
        idempotency_key: str,
    ) -> GitHubReviewRequestResult:
        connection = await self._connection(action.connection_id)
        if connection.access_token_encrypted is None:
            raise GitHubNotConnected()
        token = self.store.decrypt(connection.access_token_encrypted)
        try:
            return await GitHubConnector(
                GitHubApiClient(token, base_url=self.api_base_url, timeout=self.timeout)
            ).request_review(action, idempotency_key)
        except GitHubAuthorizationFailed:
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            raise
