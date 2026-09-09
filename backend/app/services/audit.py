from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditEvent, now


def record(
    session: AsyncSession,
    owner: UUID,
    event_type: str,
    run_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append only; caller commits this event with the corresponding domain change."""
    session.add(
        AuditEvent(
            user_id=owner,
            workflow_run_id=run_id,
            event_type=event_type,
            event_metadata=metadata or {},
            created_at=now(),
        )
    )
