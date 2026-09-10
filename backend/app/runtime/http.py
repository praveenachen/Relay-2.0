from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.runtime.client import ExecutionRequest, ExecutionSnapshot, ExecutionStatus
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


class AgentRuntimeHttpClient:
    """HTTP adapter for the separate Agent Runtime service.

    Raw HTTP responses and library exceptions stay inside this adapter. Relay
    services see only ExecutionSnapshot values or Relay-owned Runtime errors.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    async def submit_execution(self, request: ExecutionRequest) -> ExecutionSnapshot:
        payload = {
            "workflow_run_id": str(request.workflow_run_id),
            "proposed_action_id": str(request.proposed_action_id),
            "action_type": request.action_type,
            "approved_payload": request.approved_payload,
            "idempotency_key": request.idempotency_key,
            "correlation_id": request.correlation_id,
        }
        return await self._request("POST", "/executions", json=payload)

    async def get_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        return await self._request("GET", f"/executions/{execution_id}")

    async def cancel_execution(self, execution_id: UUID) -> ExecutionSnapshot:
        return await self._request("POST", f"/executions/{execution_id}/cancel", cancelling=True)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        cancelling: bool = False,
    ) -> ExecutionSnapshot:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.request(method, path, json=json, headers=headers)
        except httpx.TimeoutException as error:
            raise RuntimeRequestTimeout() from error
        except httpx.TransportError as error:
            raise RuntimeUnavailable() from error

        if response.status_code in {401, 403}:
            raise RuntimeUnauthorized()
        if response.status_code == 404:
            raise RuntimeExecutionNotFound()
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise RuntimeRateLimited(
                int(retry_after) if retry_after and retry_after.isdigit() else None
            )
        if response.status_code >= 500:
            raise RuntimeUnavailable()
        if response.status_code >= 400:
            if cancelling:
                raise RuntimeCancellationFailed()
            raise RuntimeExecutionFailed()

        try:
            data = response.json()
        except ValueError as error:
            raise RuntimeMalformedResponse() from error
        try:
            snapshot = ExecutionSnapshot.model_validate(data)
        except ValidationError as error:
            raise RuntimeMalformedResponse() from error
        if snapshot.status == ExecutionStatus.FAILED and not snapshot.error_code:
            raise RuntimeMalformedResponse()
        return snapshot
