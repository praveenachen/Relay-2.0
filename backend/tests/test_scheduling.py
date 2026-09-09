from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.models import (
    AcademicTask,
    AvailabilityWindow,
    BusyInterval,
    SchedulingPreference,
    SchedulingProblem,
    SchedulingStatus,
    StudySession,
)
from app.scheduling.solver import CPSATStudyScheduler, decompose_minutes

TZ = ZoneInfo("America/Toronto")


def dt(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


def prefs(**overrides: object) -> SchedulingPreference:
    data = {
        "timezone": "America/Toronto",
        "earliest_study_time": time(8),
        "latest_study_time": time(22),
        "preferred_session_minutes": 60,
        "maximum_session_minutes": 90,
        "minimum_break_minutes": 15,
    }
    data.update(overrides)
    return SchedulingPreference(**data)


def task(task_id: str, deadline: datetime, minutes: int = 60, priority: int = 3) -> AcademicTask:
    return AcademicTask(
        id=task_id,
        title=task_id.title(),
        course="CSC",
        deadline=deadline,
        estimated_minutes=minutes,
        priority=priority,
        status="todo",
    )


def problem(
    tasks: tuple[AcademicTask, ...],
    windows: tuple[AvailabilityWindow, ...],
    *,
    busy: tuple[BusyInterval, ...] = (),
    locked: tuple[StudySession, ...] = (),
    now: datetime | None = None,
    preference: SchedulingPreference | None = None,
) -> SchedulingProblem:
    return SchedulingProblem(
        tasks=tasks,
        availability_windows=windows,
        busy_intervals=busy,
        preferences=preference or prefs(),
        locked_sessions=locked,
        now=now or dt(1, 5, 7),
    )


def solve(item: SchedulingProblem):
    return CPSATStudyScheduler().solve(item)


def test_single_task_schedules_inside_available_window() -> None:
    result = solve(
        problem(
            (task("calculus", dt(1, 7, 17), 60),),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 12)),),
        )
    )

    assert result.status == SchedulingStatus.OPTIMAL
    assert result.metrics.tasks_fully_scheduled == 1
    assert len(result.sessions) == 1
    assert result.sessions[0].start >= dt(1, 5, 9)
    assert result.sessions[0].end <= dt(1, 5, 12)


def test_multiple_tasks_prefer_earlier_deadlines() -> None:
    result = solve(
        problem(
            (
                task("later", dt(1, 10, 17), 60, priority=1),
                task("urgent", dt(1, 6, 17), 60, priority=5),
            ),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 12)),),
        )
    )

    assert {session.task_id for session in result.sessions} == {"urgent", "later"}
    assert result.sessions[0].task_id == "urgent"


def test_overlapping_busy_intervals_are_removed_from_candidates() -> None:
    result = solve(
        problem(
            (task("systems", dt(1, 6, 17), 60),),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 12)),),
            busy=(BusyInterval(start=dt(1, 5, 9), end=dt(1, 5, 11), source_event_id="class"),),
        )
    )

    assert len(result.sessions) == 1
    assert result.sessions[0].start >= dt(1, 5, 11)


def test_decomposes_large_task_into_multiple_sessions() -> None:
    assert decompose_minutes(300, preferred=90, maximum=120) == (90, 90, 90, 30)
    result = solve(
        problem(
            (task("midterm", dt(1, 8, 17), 180),),
            (
                AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 12)),
                AvailabilityWindow(start=dt(1, 6, 9), end=dt(1, 6, 12)),
            ),
            preference=prefs(preferred_session_minutes=90, maximum_session_minutes=90),
        )
    )

    assert result.metrics.tasks_fully_scheduled == 1
    assert sum(session.duration_minutes for session in result.sessions) == 180
    assert len(result.sessions) == 2


def test_minimum_break_prevents_back_to_back_sessions() -> None:
    result = solve(
        problem(
            (
                task("a", dt(1, 6, 17), 60),
                task("b", dt(1, 6, 17), 60),
            ),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 11, 15)),),
            preference=prefs(minimum_break_minutes=15),
        )
    )

    assert len(result.sessions) == 2
    first, second = result.sessions
    assert (second.start - first.end).total_seconds() / 60 >= 15


def test_locked_session_is_preserved_and_remaining_work_regenerated() -> None:
    locked = StudySession(
        id="locked",
        task_id="essay",
        start=dt(1, 5, 9),
        end=dt(1, 5, 10),
        locked=True,
    )
    result = solve(
        problem(
            (task("essay", dt(1, 7, 17), 120),),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 13)),),
            locked=(locked,),
        )
    )

    assert result.sessions[0] == locked
    assert sum(session.duration_minutes for session in result.sessions) == 120
    assert result.unscheduled_minutes_by_task["essay"] == 0


def test_no_availability_returns_infeasible_with_unscheduled_minutes() -> None:
    result = solve(
        problem(
            (task("lab", dt(1, 6, 17), 120),),
            (),
        )
    )

    assert result.status == SchedulingStatus.INFEASIBLE
    assert result.metrics.unscheduled_minutes == 120
    assert result.conflicts[0].code == "UNSCHEDULED_WORK"


def test_deadline_before_available_time_is_infeasible() -> None:
    result = solve(
        problem(
            (task("quiz", dt(1, 5, 10), 60),),
            (AvailabilityWindow(start=dt(1, 5, 11), end=dt(1, 5, 13)),),
            now=dt(1, 5, 8),
        )
    )

    assert result.status == SchedulingStatus.INFEASIBLE
    assert result.unscheduled_minutes_by_task["quiz"] == 60


def test_cross_midnight_window_is_clipped_to_daily_study_hours() -> None:
    result = solve(
        problem(
            (task("reading", dt(1, 7, 17), 60),),
            (AvailabilityWindow(start=dt(1, 5, 21), end=dt(1, 6, 2)),),
            preference=prefs(earliest_study_time=time(20), latest_study_time=time(22)),
        )
    )

    assert len(result.sessions) == 1
    assert result.sessions[0].start.hour == 21
    assert result.sessions[0].end.hour == 22


def test_dst_boundary_uses_timezone_aware_offsets() -> None:
    before = datetime(2026, 3, 7, 20, tzinfo=TZ)
    after = datetime(2026, 3, 8, 22, tzinfo=TZ)
    result = solve(
        SchedulingProblem(
            tasks=(task("dst", datetime(2026, 3, 9, 17, tzinfo=TZ), 60),),
            availability_windows=(AvailabilityWindow(start=before, end=after),),
            busy_intervals=(),
            preferences=prefs(earliest_study_time=time(18), latest_study_time=time(22)),
            now=before,
        )
    )

    assert result.metrics.tasks_fully_scheduled == 1
    assert all(session.start.tzinfo is not None for session in result.sessions)


def test_invalid_naive_deadline_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AcademicTask(
            id="bad",
            title="Bad",
            deadline=datetime(2026, 1, 5, 12),
            estimated_minutes=30,
            priority=3,
            status="todo",
        )
