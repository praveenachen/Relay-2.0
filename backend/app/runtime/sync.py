import asyncio
from uuid import UUID

from app.runtime.client import ExecutionSnapshot, RuntimeClient
from app.runtime.errors import RuntimeExecutionNotFound, RuntimeRequestTimeout, RuntimeUnavailable
from app.runtime.state import runtime_status_is_terminal


async def poll_until_terminal(
    runtime: RuntimeClient,
    snapshot: ExecutionSnapshot,
    *,
    max_attempts: int,
    interval_seconds: float,
) -> ExecutionSnapshot:
    current = snapshot
    for _ in range(max_attempts):
        if runtime_status_is_terminal(current.status):
            return current
        if interval_seconds > 0:
            await asyncio.sleep(interval_seconds)
        try:
            current = await runtime.get_execution(current.execution_id)
        except (RuntimeRequestTimeout, RuntimeUnavailable, RuntimeExecutionNotFound):
            return current
    return current


async def cancel_runtime_execution(runtime: RuntimeClient, execution_id: UUID) -> ExecutionSnapshot:
    return await runtime.cancel_execution(execution_id)
