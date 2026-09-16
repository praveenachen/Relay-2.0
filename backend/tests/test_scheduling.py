import time as time_module
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.constraints import validate_session_adjustments
from app.scheduling.models import (
    AcademicTask,
    AvailabilityWindow,
    BusyInterval,
    SchedulingPreference,
    SchedulingProblem,
    SchedulingStatus,
    StudySession,
)
from app.scheduling.objectives import SchedulingWeights
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


def test_decomposition_never_exceeds_preferred_or_maximum() -> None:
    # preferred always bounds fragment size when preferred <= maximum (the
    # only valid configuration, enforced by SchedulingPreference); maximum
    # is a ceiling that preferred can never cross, not an active target.
    chunks = decompose_minutes(200, preferred=60, maximum=75)
    assert chunks == (60, 60, 60, 20)
    for chunk in chunks:
        assert chunk <= 60
        assert chunk <= 75


def test_short_final_chunk_is_rebalanced_without_exceeding_maximum() -> None:
    assert decompose_minutes(65, preferred=60, maximum=60) == (50, 15)


def test_priority_breaks_ties_between_equal_deadlines() -> None:
    result = solve(
        problem(
            (
                task("low", dt(1, 6, 17), 60, priority=5),
                task("high", dt(1, 6, 17), 60, priority=1),
            ),
            (AvailabilityWindow(start=dt(1, 5, 9), end=dt(1, 5, 11)),),
        )
    )

    assert result.sessions[0].task_id == "high"


def test_daily_balance_weight_spreads_large_task_across_days() -> None:
    """The balance objective should use more days than an unbalanced solve."""
    big_task = (task("project", dt(1, 12, 17), 240),)
    windows = tuple(
        AvailabilityWindow(start=dt(1, day, 8), end=dt(1, day, 22)) for day in range(5, 10)
    )
    preference = prefs(preferred_session_minutes=60, maximum_session_minutes=60)

    unbalanced = CPSATStudyScheduler(SchedulingWeights(daily_balance=0)).solve(
        problem(big_task, windows, preference=preference)
    )
    balanced = solve(problem(big_task, windows, preference=preference))

    def days_used(result) -> set:
        return {session.start.date() for session in result.sessions}

    assert len(days_used(unbalanced)) < len(days_used(balanced))
    assert len(days_used(balanced)) == 4


def test_three_same_task_sessions_are_spread_when_days_are_available() -> None:
    result = solve(
        problem(
            (task("project", dt(1, 9, 17), 180),),
            tuple(
                AvailabilityWindow(start=dt(1, day, 9), end=dt(1, day, 13)) for day in range(5, 8)
            ),
            preference=prefs(preferred_session_minutes=60, maximum_session_minutes=60),
        )
    )

    assert result.metrics.tasks_fully_scheduled == 1
    assert len({session.start.date() for session in result.sessions}) == 3


def test_urgent_task_can_use_three_sessions_on_same_day() -> None:
    result = solve(
        problem(
            (task("urgent", dt(1, 5, 14), 180),),
            (AvailabilityWindow(start=dt(1, 5, 8), end=dt(1, 5, 14)),),
            now=dt(1, 5, 7),
            preference=prefs(preferred_session_minutes=60, maximum_session_minutes=60),
        )
    )

    assert result.metrics.tasks_fully_scheduled == 1
    assert len(result.sessions) == 3
    assert {session.start.date() for session in result.sessions} == {dt(1, 5, 8).date()}


def test_manual_move_rejects_busy_time_and_accepts_clear_time() -> None:
    scheduling_problem = problem(
        (task("essay", dt(1, 7, 17), 60),),
        (AvailabilityWindow(start=dt(1, 5, 8), end=dt(1, 6, 22)),),
        busy=(BusyInterval(start=dt(1, 5, 10), end=dt(1, 5, 11), source_event_id="private"),),
    )
    blocked = StudySession(
        id="essay-1",
        task_id="essay",
        start=dt(1, 5, 10),
        end=dt(1, 5, 11),
    )
    clear = blocked.model_copy(update={"start": dt(1, 6, 10), "end": dt(1, 6, 11)})

    blocked_report = validate_session_adjustments(scheduling_problem, (blocked,))
    clear_report = validate_session_adjustments(scheduling_problem, (clear,))

    assert not blocked_report.valid
    assert blocked_report.message == "That time overlaps a Busy calendar interval."
    assert clear_report.valid


def test_month_long_window_with_wide_study_hours_solves_quickly() -> None:
    """Regression for a real production hang: a ~1-month planning window
    with a wide daily study range (11am-10pm) and a handful of tasks
    produces tens of thousands of 15-minute candidate slots. The naive
    all-pairs overlap check compared every candidate against every other
    candidate regardless of how many days apart they were, which is
    O(candidates^2) and took long enough to freeze the single-threaded
    server for every user, not just this request. Candidates can only ever
    overlap something on the same or the very next calendar day, so this
    should stay fast regardless of how long the window is."""
    month_window = (AvailabilityWindow(start=dt(1, 1, 0), end=dt(1, 31, 0)),)
    preference = prefs(earliest_study_time=time(11), latest_study_time=time(22))
    tasks = tuple(
        task(f"task-{index}", dt(1, 28, 20), minutes=300, priority=(index % 5) + 1)
        for index in range(6)
    )

    started = time_module.perf_counter()
    result = solve(problem(tasks, month_window, preference=preference, now=dt(1, 1, 11)))
    elapsed = time_module.perf_counter() - started

    # The old O(n^2) all-pairs comparison over tens of thousands of
    # candidates took multiple minutes on this scenario; day-grouping
    # should bring it back to roughly the CP-SAT search cap.
    assert elapsed < 15
    assert result.status != SchedulingStatus.INFEASIBLE
    assert result.sessions
