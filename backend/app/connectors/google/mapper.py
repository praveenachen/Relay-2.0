from datetime import datetime
from typing import Any

from app.scheduling.models import BusyInterval


def parse_google_datetime(value: dict[str, Any]) -> datetime:
    raw = value.get("dateTime") or value.get("date")
    if not isinstance(raw, str):
        raise ValueError("Google datetime is missing")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Google datetime must be timezone-aware")
    return parsed


def busy_interval_from_event(item: dict[str, Any]) -> BusyInterval:
    return BusyInterval(
        start=parse_google_datetime(item.get("start", {})),
        end=parse_google_datetime(item.get("end", {})),
        source_event_id=item.get("id") if isinstance(item.get("id"), str) else None,
    )
