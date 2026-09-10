from uuid import UUID, uuid4

import httpx
import pytest

from app.runtime.client import ExecutionRequest, ExecutionStatus
from app.runtime.errors import (
    RuntimeCancellationFailed,
    RuntimeExecutionFailed,
    RuntimeExecutionNotFound,
    RuntimeMalformedResponse,
    RuntimeRateLimited,
    RuntimeRequestTimeout,
    RuntimeUnauthorized,
    RuntimeUnavailable,
)
from app.runtime.http import AgentRuntimeHttpClient


def request() -> ExecutionRequest:
    run_id = uuid4()
    action_id = uuid4()
    return ExecutionRequest(
        workflow_run_id=run_id,
        proposed_action_id=action_id,
        action_type="create_notion_task",
        approved_payload={"title": "Ship", "connection_id": str(uuid4())},
        idempotency_key=f"collaborate:{run_id}:{action_id}",
        correlation_id=f"collaborate:{run_id}:{action_id}",
    )


def response_payload(
    execution_id: UUID | None = None, status: str = "succeeded"
) -> dict[str, object]:
    return {
        "execution_id": str(execution_id or uuid4()),
        "status": status,
        "result": {"external_id": "x-1", "external_url": "https://example.test/x-1"},
    }


@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (401, RuntimeUnauthorized),
        (403, RuntimeUnauthorized),
        (404, RuntimeExecutionNotFound),
        (409, RuntimeExecutionFailed),
        (500, RuntimeUnavailable),
    ],
)
async def test_http_errors_are_normalized(
    monkeypatch, status_code: int, error: type[Exception]
) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(status_code, json={"error": "no"}))
    with pytest.raises(error):
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).submit_execution(request())


async def test_submit_success_sends_approved_payload_and_idempotency() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["authorization"] = req.headers["authorization"]
        seen["body"] = req.read().decode()
        return httpx.Response(200, json=response_payload(status="queued"))

    transport = httpx.MockTransport(handler)
    payload = request()
    snapshot = await AgentRuntimeHttpClient(
        "https://runtime.test", "secret", transport=transport
    ).submit_execution(payload)
    assert snapshot.status == ExecutionStatus.QUEUED
    assert seen["authorization"] == "Bearer secret"
    assert '"approved_payload"' in str(seen["body"])
    assert payload.idempotency_key in str(seen["body"])
    assert '"connection_id"' in str(seen["body"])


@pytest.mark.parametrize("status", ["queued", "running", "succeeded", "failed", "cancelled"])
async def test_get_execution_statuses(status: str) -> None:
    execution_id = uuid4()
    payload = response_payload(execution_id, status=status)
    if status == "failed":
        payload["error_code"] = "PROVIDER_FAILED"
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    snapshot = await AgentRuntimeHttpClient(
        "https://runtime.test", "secret", transport=transport
    ).get_execution(execution_id)
    assert snapshot.execution_id == execution_id
    assert snapshot.status == ExecutionStatus(status)


async def test_cancel_execution() -> None:
    execution_id = uuid4()
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=response_payload(execution_id, status="cancelled"))
    )
    snapshot = await AgentRuntimeHttpClient(
        "https://runtime.test", "secret", transport=transport
    ).cancel_execution(execution_id)
    assert snapshot.status == ExecutionStatus.CANCELLED


async def test_cancel_failure_is_specific() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(RuntimeCancellationFailed):
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).cancel_execution(uuid4())


async def test_timeout_is_not_execution_failure() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    transport = httpx.MockTransport(handler)
    with pytest.raises(RuntimeRequestTimeout):
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).submit_execution(request())


async def test_transport_error_is_runtime_unavailable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=req)

    transport = httpx.MockTransport(handler)
    with pytest.raises(RuntimeUnavailable):
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).submit_execution(request())


@pytest.mark.parametrize(
    "response", [httpx.Response(200, text="not-json"), httpx.Response(200, json={"bad": True})]
)
async def test_malformed_response(response: httpx.Response) -> None:
    transport = httpx.MockTransport(lambda req: response)
    with pytest.raises(RuntimeMalformedResponse):
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).submit_execution(request())


async def test_runtime_rate_limit_preserves_retry_after() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(429, headers={"retry-after": "12"}, json={"error": "slow"})
    )
    with pytest.raises(RuntimeRateLimited) as raised:
        await AgentRuntimeHttpClient(
            "https://runtime.test", "secret", transport=transport
        ).submit_execution(request())
    assert raised.value.retry_after_seconds == 12
