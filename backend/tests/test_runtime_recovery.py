from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import func, select
from test_collaborate import _mock_repository_facts, analyzed_run, approve_all
from test_learn import approve, ready

from app.core.config import get_settings
from app.domain.enums import WorkflowStatus as S
from app.models.entities import ExternalArtifact, ProposedAction, WorkflowRun
from app.repositories.relay import RelayRepository
from app.runtime.client import ExecutionRequest, ExecutionSnapshot
from app.runtime.errors import RuntimeRateLimited, RuntimeRequestTimeout, RuntimeUnavailable
from app.services.execution import ExecutionService
from app.workflows.project_meeting.execution import CollaborateExecutionService


def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        get_settings(),
        "token_encryption_key",
        type("Secret", (), {"get_secret_value": lambda self: key})(),
    )
    return key


class UnavailableRuntime:
    def __init__(self):
        self.requests: list[ExecutionRequest] = []

    async def submit_execution(self, request: ExecutionRequest) -> ExecutionSnapshot:
        self.requests.append(request)
        raise RuntimeUnavailable()

    async def get_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        raise RuntimeRequestTimeout()

    async def cancel_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        raise RuntimeUnavailable()


async def test_learn_runtime_outage_preserves_approved_payload_and_key(
    client, account, session_factory
):
    _path, detail = await ready(client)
    approved = await approve(client, detail)
    runtime = UnavailableRuntime()
    run_id = UUID(detail["run"]["id"])
    owner = UUID(account["id"])

    async with session_factory() as session:
        result = await ExecutionService(RelayRepository(session), runtime).execute(run_id, owner)
        assert result.status == S.EXECUTING
        assert result.error_code == "RUNTIME_UNAVAILABLE"
        assert runtime.requests[0].approved_payload == approved["approved_payload"]
        assert runtime.requests[0].idempotency_key == f"learn:{run_id}:{approved['id']}"
        stored = await session.get(WorkflowRun, run_id)
        assert stored is not None
        assert stored.status == S.EXECUTING

    async with session_factory() as session:
        retry = await ExecutionService(RelayRepository(session), runtime).execute(run_id, owner)
        assert retry.status == S.EXECUTING
        assert len(runtime.requests) == 2
        assert runtime.requests[1].approved_payload == runtime.requests[0].approved_payload
        assert runtime.requests[1].idempotency_key == runtime.requests[0].idempotency_key


async def test_collaborate_retry_skips_existing_artifact(
    client, account, session_factory, monkeypatch
):
    _mock_repository_facts(monkeypatch)
    path, detail, _project = await analyzed_run(
        client, session_factory, account, encryption_key(monkeypatch)
    )
    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    detail = requested.json()
    await approve_all(client, detail)
    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text

    async with session_factory() as session:
        count_before = await session.scalar(select(func.count()).select_from(ExternalArtifact))

    again = await client.post(path + "/execute")
    assert again.status_code == 200, again.text
    async with session_factory() as session:
        count_after = await session.scalar(select(func.count()).select_from(ExternalArtifact))
        local_actions = await session.scalar(select(func.count()).select_from(ProposedAction))
        assert count_after == count_before
        assert local_actions == len(detail["approvals"])


async def test_collaborate_runtime_outage_remains_retryable(
    client, account, session_factory, monkeypatch
):
    _mock_repository_facts(monkeypatch)
    path, detail, _project = await analyzed_run(
        client, session_factory, account, encryption_key(monkeypatch)
    )
    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    detail = requested.json()
    await approve_all(client, detail)
    runtime = UnavailableRuntime()
    run_id = UUID(detail["run"]["id"])
    owner = UUID(account["id"])

    async with session_factory() as session:
        result = await CollaborateExecutionService(RelayRepository(session), runtime).execute(
            run_id, owner
        )
        assert result.status in {S.QUEUED, S.EXECUTING}
        assert result.result_payload["succeeded_count"] == 0
        assert result.result_payload["total_count"] == len(detail["approvals"])

    async with session_factory() as session:
        retry = await CollaborateExecutionService(RelayRepository(session), runtime).execute(
            run_id, owner
        )
        assert retry.status in {S.QUEUED, S.EXECUTING}
        approval_count = len(detail["approvals"])
        assert len(runtime.requests) == approval_count * 2
        assert [req.idempotency_key for req in runtime.requests[:approval_count]] == [
            req.idempotency_key for req in runtime.requests[approval_count:]
        ]


def test_recoverable_runtime_errors_are_explicit() -> None:
    assert RuntimeUnavailable.code == "RUNTIME_UNAVAILABLE"
    assert RuntimeRequestTimeout.code == "RUNTIME_REQUEST_TIMEOUT"
    assert RuntimeRateLimited.code == "RUNTIME_RATE_LIMITED"
