from datetime import UTC, datetime
from typing import Any

from app.scheduling.models import BusyInterval


def parse_google_datetime(value: dict[str, Any]) -> datetime:
    """Parse a Google Calendar event boundary.

    All-day events report a bare ``date`` (no time or offset) instead of
    ``dateTime``. Relay has no reliable timezone for those, so it treats the
    boundary as UTC midnight rather than raising and losing the whole
    availability fetch over one all-day event.
    """
    raw = value.get("dateTime")
    if isinstance(raw, str):
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Google datetime must be timezone-aware")
        return parsed
    raw = value.get("date")
    if isinstance(raw, str):
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    raise ValueError("Google datetime is missing")


def busy_interval_from_event(item: dict[str, Any]) -> BusyInterval:
    return BusyInterval(
        start=parse_google_datetime(item.get("start", {})),
        end=parse_google_datetime(item.get("end", {})),
        source_event_id=item.get("id") if isinstance(item.get("id"), str) else None,
    )
