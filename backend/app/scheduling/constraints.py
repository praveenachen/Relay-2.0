from dataclasses import dataclass
from datetime import datetime

from app.scheduling.models import BusyInterval, StudySession


@dataclass(frozen=True)
class HardConstraintReport:
    valid: bool
    message: str | None = None


def overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and other_start < end


def session_overlaps_busy(session: StudySession, busy: BusyInterval) -> bool:
    return overlaps(session.start, session.end, busy.start, busy.end)


def validate_no_overlap(sessions: tuple[StudySession, ...]) -> HardConstraintReport:
    ordered = sorted(sessions, key=lambda item: item.start)
    for left, right in zip(ordered, ordered[1:], strict=False):
        if overlaps(left.start, left.end, right.start, right.end):
            return HardConstraintReport(False, "study sessions overlap")
    return HardConstraintReport(True)
