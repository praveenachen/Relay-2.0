from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduling.models import BusyInterval, SchedulingProblem, StudySession


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


def validate_session_adjustments(
    problem: SchedulingProblem, sessions: tuple[StudySession, ...]
) -> HardConstraintReport:
    """Validate user-moved blocks against the solver's hard boundaries."""
    tasks = {task.id: task for task in problem.tasks}
    seen_ids: set[str] = set()
    totals: dict[str, int] = {}
    zone = ZoneInfo(problem.preferences.timezone)
    earliest = problem.preferences.earliest_study_time
    latest = problem.preferences.latest_study_time

    for session in sessions:
        task = tasks.get(session.task_id)
        if task is None:
            return HardConstraintReport(False, "That time block no longer belongs to this plan.")
        if session.id is not None:
            if session.id in seen_ids:
                return HardConstraintReport(False, "The schedule contains a duplicate time block.")
            seen_ids.add(session.id)
        if session.end > task.deadline:
            return HardConstraintReport(False, "That time would place the task after its deadline.")
        if session.duration_minutes > problem.preferences.maximum_session_minutes:
            return HardConstraintReport(
                False,
                "That block is longer than your maximum session length.",
            )
        if not any(
            window.start <= session.start and session.end <= window.end
            for window in problem.availability_windows
        ):
            return HardConstraintReport(False, "That time is outside this planning window.")
        local_start = session.start.astimezone(zone)
        local_end = session.end.astimezone(zone)
        if (
            local_start.date() != local_end.date()
            or local_start.timetz().replace(tzinfo=None) < earliest
            or local_end.timetz().replace(tzinfo=None) > latest
            or (not problem.preferences.weekend_available and local_start.weekday() >= 5)
        ):
            return HardConstraintReport(False, "That time is outside your available hours.")
        if any(session_overlaps_busy(session, busy) for busy in problem.busy_intervals):
            return HardConstraintReport(False, "That time overlaps a Busy calendar interval.")
        totals[task.id] = totals.get(task.id, 0) + session.duration_minutes

    for task_id, minutes in totals.items():
        if minutes > tasks[task_id].estimated_minutes:
            return HardConstraintReport(
                False,
                "Those blocks exceed the task's estimated time.",
            )

    ordered = sorted(sessions, key=lambda item: item.start)
    minimum_break = problem.preferences.minimum_break_minutes
    for left, right in zip(ordered, ordered[1:], strict=False):
        gap_minutes = (right.start - left.end).total_seconds() / 60
        if gap_minutes < 0:
            return HardConstraintReport(False, "Relay time blocks cannot overlap.")
        if gap_minutes < minimum_break:
            return HardConstraintReport(
                False,
                f"Leave at least {minimum_break} minutes between Relay blocks.",
            )
    return HardConstraintReport(True)
