from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditEvent, now

# `AuditEvent.id` is a random UUID, not a sequence, so `order_by(created_at,
# id)` only produces a stable order when created_at is strictly increasing.
# Several audit events can be recorded within the same synchronous call
# (e.g. two WORKFLOW_STATE_CHANGED transitions inside one solve()/summarize()
# call), fast enough on some clocks to collide on wall-clock resolution --
# which then sorts those events by random UUID instead of the order they
# actually happened in. This module-level watermark guarantees each event
# gets a strictly later timestamp than the previous one recorded in this
# process, without a schema change. Safe without locking: this function is
# synchronous with no `await` inside it, so nothing can interleave between
# the read and the write on a single-process async event loop.
_last_recorded_at: datetime | None = None


def record(
    session: AsyncSession,
    owner: UUID,
    event_type: str,
    run_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append only; caller commits this event with the corresponding domain change."""
    global _last_recorded_at
    instant = now()
    if _last_recorded_at is not None and instant <= _last_recorded_at:
        instant = _last_recorded_at + timedelta(microseconds=1)
    _last_recorded_at = instant
    session.add(
        AuditEvent(
            user_id=owner,
            workflow_run_id=run_id,
            event_type=event_type,
            event_metadata=metadata or {},
            created_at=instant,
        )
    )
