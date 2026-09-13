from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from app.scheduling.constraints import overlaps
from app.scheduling.models import (
    AcademicTask,
    AvailabilityWindow,
    BusyInterval,
    SchedulingConflict,
    SchedulingMetrics,
    SchedulingPreference,
    SchedulingProblem,
    SchedulingResult,
    SchedulingStatus,
    StudySession,
)
from app.scheduling.objectives import DEFAULT_WEIGHTS, SchedulingWeights

SLOT_MINUTES = 15
MAX_SOLVER_SECONDS = 5.0


@dataclass(frozen=True)
class CandidateSlot:
    task: AcademicTask
    start: datetime
    end: datetime
    fragment_id: int
    duration_minutes: int
    score: int


@dataclass(frozen=True)
class FreeWindow:
    start: datetime
    end: datetime


def _combine_date_time(day: datetime, value: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day.date(), value, tzinfo=zone)


def _ceil_to_slot(moment: datetime) -> datetime:
    remainder = moment.minute % SLOT_MINUTES
    if remainder == 0 and moment.second == 0 and moment.microsecond == 0:
        return moment.replace(second=0, microsecond=0)
    delta = SLOT_MINUTES - remainder
    return (moment + timedelta(minutes=delta)).replace(second=0, microsecond=0)


def _floor_to_slot(moment: datetime) -> datetime:
    return (moment - timedelta(minutes=moment.minute % SLOT_MINUTES)).replace(
        second=0, microsecond=0
    )


def decompose_minutes(total: int, preferred: int, maximum: int) -> tuple[int, ...]:
    if total <= 0:
        return ()
    target = min(preferred, maximum)
    chunks: list[int] = []
    remaining = total
    while remaining > target:
        chunks.append(target)
        remaining -= target
    if remaining > 0:
        chunks.append(remaining)
    if len(chunks) >= 2 and chunks[-1] < SLOT_MINUTES:
        chunks[-2] += chunks[-1]
        chunks.pop()
    return tuple(chunks)


def _clip_to_study_windows(
    windows: tuple[AvailabilityWindow, ...], preferences: SchedulingPreference
) -> list[FreeWindow]:
    zone = ZoneInfo(preferences.timezone)
    clipped: list[FreeWindow] = []
    for window in windows:
        local_start = window.start.astimezone(zone)
        local_end = window.end.astimezone(zone)
        cursor_day = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = local_end.replace(hour=0, minute=0, second=0, microsecond=0)
        while cursor_day <= last_day:
            if preferences.weekend_available or cursor_day.weekday() < 5:
                allowed_start = _combine_date_time(
                    cursor_day, preferences.earliest_study_time, zone
                )
                allowed_end = _combine_date_time(cursor_day, preferences.latest_study_time, zone)
                start = max(local_start, allowed_start).astimezone(window.start.tzinfo)
                end = min(local_end, allowed_end).astimezone(window.end.tzinfo)
                if start < end:
                    clipped.append(FreeWindow(_ceil_to_slot(start), _floor_to_slot(end)))
            cursor_day += timedelta(days=1)
    return [item for item in clipped if item.start < item.end]


def _subtract_busy(
    windows: list[FreeWindow], busy_intervals: tuple[BusyInterval, ...]
) -> list[FreeWindow]:
    free = windows
    for busy in busy_intervals:
        updated: list[FreeWindow] = []
        for window in free:
            if not overlaps(window.start, window.end, busy.start, busy.end):
                updated.append(window)
                continue
            if window.start < busy.start:
                updated.append(
                    FreeWindow(window.start, min(window.end, _floor_to_slot(busy.start)))
                )
            if busy.end < window.end:
                updated.append(FreeWindow(max(window.start, _ceil_to_slot(busy.end)), window.end))
        free = [item for item in updated if item.start < item.end]
    return free


def _subtract_locked(
    windows: list[FreeWindow], locked: tuple[StudySession, ...]
) -> list[FreeWindow]:
    busy = tuple(
        BusyInterval(start=item.start, end=item.end, source_event_id=item.id) for item in locked
    )
    return _subtract_busy(windows, busy)


def _slot_score(
    task: AcademicTask,
    start: datetime,
    duration_minutes: int,
    preferences: SchedulingPreference,
    weights: SchedulingWeights,
    urgency_anchor: datetime,
) -> int:
    zone = ZoneInfo(preferences.timezone)
    local = start.astimezone(zone)
    hours_until_deadline = max(
        1,
        int((task.deadline - urgency_anchor).total_seconds() // 3600),
    )
    urgency_rank = max(0, 168 - hours_until_deadline)
    urgency = urgency_rank * weights.deadline_urgency
    priority_rank = 6 - task.priority
    priority = priority_rank * weights.priority
    minutes_after_now = max(0, int((start - urgency_anchor).total_seconds() // 60))
    earliness = -(minutes_after_now // SLOT_MINUTES) * max(1, urgency_rank + priority_rank)
    preferred = 0
    if preferences.preferred_period == "morning" and 7 <= local.hour < 12:
        preferred = weights.preferred_period
    elif preferences.preferred_period == "afternoon" and 12 <= local.hour < 17:
        preferred = weights.preferred_period
    elif preferences.preferred_period == "evening" and 17 <= local.hour < 22:
        preferred = weights.preferred_period
    # Heuristic, not empirically tuned: reward candidate slots that fill a
    # full preferred-length block instead of leaving the solver free to pick
    # an oddly-sized leftover fragment when a clean block would fit as well.
    fragmentation = (
        weights.fragmentation if duration_minutes >= preferences.preferred_session_minutes else 0
    )
    return urgency + priority + earliness + preferred + fragmentation


def _local_day(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def _locked_minutes_by_task(locked: tuple[StudySession, ...]) -> dict[str, int]:
    minutes: dict[str, int] = {}
    for session in locked:
        minutes[session.task_id] = minutes.get(session.task_id, 0) + session.duration_minutes
    return minutes


class CPSATStudyScheduler:
    def __init__(self, weights: SchedulingWeights = DEFAULT_WEIGHTS):
        self.weights = weights

    def solve(self, problem: SchedulingProblem) -> SchedulingResult:
        locked_minutes = _locked_minutes_by_task(problem.locked_sessions)
        free = _clip_to_study_windows(problem.availability_windows, problem.preferences)
        free = _subtract_busy(free, problem.busy_intervals)
        free = _subtract_locked(free, problem.locked_sessions)
        candidates = self._candidate_slots(problem, free, locked_minutes)
        if not candidates and any(
            task.estimated_minutes > locked_minutes.get(task.id, 0) for task in problem.tasks
        ):
            return self._result(problem, (), locked_minutes, SchedulingStatus.INFEASIBLE)

        model = cp_model.CpModel()
        selected = [model.new_bool_var(f"slot_{index}") for index, _ in enumerate(candidates)]
        for left_index, left in enumerate(candidates):
            for right_index in range(left_index + 1, len(candidates)):
                right = candidates[right_index]
                break_until = left.end + timedelta(
                    minutes=problem.preferences.minimum_break_minutes
                )
                if overlaps(left.start, break_until, right.start, right.end) or overlaps(
                    right.start,
                    right.end + timedelta(minutes=problem.preferences.minimum_break_minutes),
                    left.start,
                    left.end,
                ):
                    model.add(selected[left_index] + selected[right_index] <= 1)

        for task in problem.tasks:
            requirement = max(0, task.estimated_minutes - locked_minutes.get(task.id, 0))
            task_vars = [
                selected[index] * candidate.duration_minutes
                for index, candidate in enumerate(candidates)
                if candidate.task.id == task.id
            ]
            if task_vars:
                model.add(sum(task_vars) <= requirement)

        objective_terms = []
        for index, candidate in enumerate(candidates):
            scheduled_value = candidate.duration_minutes * self.weights.unscheduled_minute
            objective_terms.append(selected[index] * (scheduled_value + candidate.score))
        objective_terms.extend(
            self._daily_balance_penalties(model, candidates, selected, problem, locked_minutes)
        )
        model.maximize(sum(objective_terms) if objective_terms else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = MAX_SOLVER_SECONDS
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._result(problem, (), locked_minutes, SchedulingStatus.INFEASIBLE)

        sessions = [
            StudySession(
                id=f"{candidate.task.id}:{candidate.fragment_id}:{candidate.start.isoformat()}",
                task_id=candidate.task.id,
                start=candidate.start,
                end=candidate.end,
            )
            for index, candidate in enumerate(candidates)
            if solver.boolean_value(selected[index])
        ]
        result_status = (
            SchedulingStatus.OPTIMAL if status == cp_model.OPTIMAL else SchedulingStatus.FEASIBLE
        )
        return self._result(
            problem,
            tuple(sorted(sessions, key=lambda item: item.start)),
            locked_minutes,
            result_status,
        )

    def _daily_balance_penalties(
        self,
        model: cp_model.CpModel,
        candidates: list[CandidateSlot],
        selected: list[Any],
        problem: SchedulingProblem,
        locked_minutes: dict[str, int],
    ) -> list[Any]:
        """Soft penalty (heuristic, not empirically tuned) for days that carry
        more than a fair share of the remaining workload, so large tasks
        spread across the available window instead of clustering on one day.

        The fair share is based on total *required* minutes across tasks,
        not the number of candidate slots -- candidates are alternative
        start-time options for the same work, not additional work, so
        summing their durations would wildly overstate the target.
        """
        if not candidates or self.weights.daily_balance <= 0:
            return []
        zone = ZoneInfo(problem.preferences.timezone)
        day_groups: dict[date, list[int]] = {}
        for index, candidate in enumerate(candidates):
            day_groups.setdefault(_local_day(candidate.start, zone), []).append(index)
        if len(day_groups) < 2:
            return []
        total_required = sum(
            max(0, task.estimated_minutes - locked_minutes.get(task.id, 0))
            for task in problem.tasks
        )
        if total_required == 0:
            return []
        daily_target = total_required // len(day_groups)
        penalties = []
        for day, indices in day_groups.items():
            day_total = sum(selected[i] * candidates[i].duration_minutes for i in indices)
            overage = model.new_int_var(0, total_required, f"overage_{day.isoformat()}")
            model.add(overage >= day_total - daily_target)
            penalties.append(-overage * self.weights.daily_balance)
        return penalties

    def _candidate_slots(
        self,
        problem: SchedulingProblem,
        free_windows: list[FreeWindow],
        locked_minutes: dict[str, int],
    ) -> list[CandidateSlot]:
        candidates: list[CandidateSlot] = []
        for task in sorted(
            problem.tasks, key=lambda item: (item.deadline, item.priority, item.title)
        ):
            remaining = max(0, task.estimated_minutes - locked_minutes.get(task.id, 0))
            for fragment_id, minutes in enumerate(
                decompose_minutes(
                    remaining,
                    problem.preferences.preferred_session_minutes,
                    problem.preferences.maximum_session_minutes,
                )
            ):
                duration = timedelta(minutes=minutes)
                for window in free_windows:
                    latest_start = min(window.end - duration, task.deadline - duration)
                    start = max(window.start, problem.now)
                    start = _ceil_to_slot(start)
                    while start <= latest_start:
                        end = start + duration
                        candidates.append(
                            CandidateSlot(
                                task=task,
                                start=start,
                                end=end,
                                fragment_id=fragment_id,
                                duration_minutes=minutes,
                                score=_slot_score(
                                    task,
                                    start,
                                    minutes,
                                    problem.preferences,
                                    self.weights,
                                    problem.now,
                                ),
                            )
                        )
                        start += timedelta(minutes=SLOT_MINUTES)
        return candidates

    def _result(
        self,
        problem: SchedulingProblem,
        new_sessions: tuple[StudySession, ...],
        locked_minutes: dict[str, int],
        status: SchedulingStatus,
    ) -> SchedulingResult:
        scheduled: dict[str, int] = dict(locked_minutes)
        for session in new_sessions:
            scheduled[session.task_id] = (
                scheduled.get(session.task_id, 0) + session.duration_minutes
            )
        unscheduled = {
            task.id: max(0, task.estimated_minutes - scheduled.get(task.id, 0))
            for task in problem.tasks
        }
        conflicts = tuple(
            SchedulingConflict(
                code="UNSCHEDULED_WORK",
                message=(
                    "Relay scheduled "
                    f"{task.estimated_minutes - unscheduled[task.id]} of "
                    f"{task.estimated_minutes} required minutes before the deadline."
                ),
                task_id=task.id,
                unscheduled_minutes=unscheduled[task.id],
            )
            for task in problem.tasks
            if unscheduled[task.id] > 0
        )
        complete = sum(1 for task in problem.tasks if unscheduled[task.id] == 0)
        partial = sum(
            1 for task in problem.tasks if 0 < unscheduled[task.id] < task.estimated_minutes
        )
        total_session_minutes = sum(item.duration_minutes for item in new_sessions)
        metrics = SchedulingMetrics(
            tasks_fully_scheduled=complete,
            tasks_partially_scheduled=partial,
            unscheduled_minutes=sum(unscheduled.values()),
            session_count=len(new_sessions) + len(problem.locked_sessions),
            average_session_minutes=(
                total_session_minutes / len(new_sessions) if new_sessions else 0
            ),
            deadline_violations=0,
            preference_violations=0,
        )
        final_status = SchedulingStatus.INFEASIBLE if conflicts and not new_sessions else status
        return SchedulingResult(
            status=final_status,
            sessions=tuple(
                sorted((*problem.locked_sessions, *new_sessions), key=lambda item: item.start)
            ),
            conflicts=conflicts,
            metrics=metrics,
            unscheduled_minutes_by_task=unscheduled,
        )
