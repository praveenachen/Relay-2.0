from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ActionStatus
from app.domain.enums import WorkflowStatus as S
from app.models.entities import WorkflowRun
from app.runtime.errors import RuntimeRateLimited, RuntimeRequestTimeout, RuntimeUnavailable
from app.services.audit import record

RECOVERABLE_RUNTIME_ERRORS = (RuntimeRequestTimeout, RuntimeUnavailable, RuntimeRateLimited)
RECOVERABLE_RUNTIME_ERROR_CODES = {error.code for error in RECOVERABLE_RUNTIME_ERRORS}


def run_has_recoverable_runtime_error(run: WorkflowRun) -> bool:
    return (
        run.status in {S.QUEUED, S.EXECUTING} and run.error_code in RECOVERABLE_RUNTIME_ERROR_CODES
    )


def mark_runtime_recoverable(
    session: AsyncSession,
    owner: UUID,
    run: WorkflowRun,
    action_status: ActionStatus,
    *,
    action_id: UUID,
    correlation_id: str,
    error_code: str,
) -> None:
    run.status = S.QUEUED if action_status == ActionStatus.QUEUED else S.EXECUTING
    run.error_code = error_code
    run.error_message = (
        "Execution status is uncertain. Retry will reuse the approved payload and idempotency key."
    )
    record(
        session,
        owner,
        "RUNTIME_RECOVERABLE_FAILURE",
        run.id,
        {"action_id": str(action_id), "correlation_id": correlation_id, "error_code": error_code},
    )
