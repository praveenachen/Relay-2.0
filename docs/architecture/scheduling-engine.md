# Scheduling engine

`backend/app/scheduling/` is a self-contained domain package. It imports nothing from FastAPI, React, the Notion SDK, the Google SDK, or OpenAI -- it only knows about its own types (`app/scheduling/models.py`) and Google OR-Tools CP-SAT. Higher layers (`app/workflows/study_plan/service.py`) are responsible for turning Notion pages and Google Calendar events into those types before calling in, and for turning `SchedulingResult` back into whatever the API/UI need.

## Why CP-SAT, not an LLM

Study scheduling is a constrained optimization problem with a small, well-defined search space (which 15-minute slot, for which task fragment, subject to deadlines, study hours, and no overlap). CP-SAT finds a provably optimal or feasible solution against that model in milliseconds to a few seconds. An LLM has no such guarantee -- it can silently violate a deadline, double-book a slot, or ignore a break preference, and it would do so differently on every call. The project's core constraint, "AI may interpret information, but actual calendar scheduling must be deterministic," is enforced structurally here: nothing between `SchedulingProblem` going in and `SchedulingResult` coming out calls a language model.

## Domain types

`AcademicTask`, `StudyRequirement`, `AvailabilityWindow`, `BusyInterval`, `StudySession`, `SchedulingPreference`, `SchedulingProblem`, `SchedulingResult`, `SchedulingConflict`, and `SchedulingMetrics` are Relay-owned Pydantic models (`extra="forbid"`, frozen). They validate their own invariants close to the data: every timestamp must be timezone-aware, an availability window's start must precede its end, `preferred_session_minutes` cannot exceed `maximum_session_minutes`. This is what "the scheduling engine must not operate on raw Notion/Google/OpenAI objects" means in practice -- by the time anything reaches `CPSATStudyScheduler.solve`, it is one of these validated types.

## Hard constraints

Modeled directly as CP-SAT constraints, not scores:

- **No overlap, including a minimum break.** Every pair of candidate slots that would overlap (accounting for `minimum_break_minutes` on both sides) gets a `selected[i] + selected[j] <= 1` constraint.
- **No study after the deadline.** A candidate slot's latest legal start is `min(window.end - duration, task.deadline - duration)`; candidates past the deadline are never generated.
- **Only inside permitted study hours.** `_clip_to_study_windows` clips every availability window to `[earliest_study_time, latest_study_time]` per local day before any candidates are generated, and drops weekend days when `weekend_available` is false.
- **No overlap with existing calendar events.** `_subtract_busy` removes any part of a free window that overlaps a `BusyInterval`.
- **Locked sessions stay fixed.** `_subtract_locked` treats locked sessions as busy intervals (so nothing else can be scheduled over them) and the per-task minute requirement is reduced by the minutes already covered by locked sessions for that task; locked sessions are always included, unmodified, in the result.
- **Total scheduled minutes per task never exceed what's required.** `sum(selected slot minutes for task) <= remaining requirement`.

`app/scheduling/constraints.py` holds the small, pure predicates (`overlaps`, `validate_no_overlap`) used to assert these invariants in tests.

## Soft constraints (the objective)

Every soft preference is a weight in `app/scheduling/objectives.py::SchedulingWeights`, applied as a per-candidate score or an aggregate penalty inside `CPSATStudyScheduler`. None of these weights were empirically tuned against real usage data -- they are starting-point heuristics, and `daily_balance` in particular is intentionally exercised in `tests/test_scheduling.py::test_daily_balance_weight_spreads_large_task_across_days` and `docs/experiments/daily-balance-weight.md` to make that explicit.

| Weight | Effect |
| --- | --- |
| `unscheduled_minute` | Dominant term: always prefer scheduling more of a task's required minutes over less. |
| `deadline_urgency` | Rewards slots within 7 days of a task's deadline, more so the closer they are. |
| `priority` | Rewards a task's higher-priority (lower-numbered) sessions. |
| `preferred_period` | Rewards slots inside the student's preferred morning/afternoon/evening window. |
| `fragmentation` | Rewards a candidate whose duration is at least the preferred session length, so the solver doesn't gratuitously choose a smaller fragment when a clean one fits. |
| `daily_balance` | Penalizes a day whose selected minutes exceed a fair per-day share of the *task-level* remaining work (not the candidate count -- see the comment in `_daily_balance_penalties`), pushing large tasks to spread across the available window instead of clustering on whichever single day scores highest on urgency. |

All per-candidate terms sum linearly into one CP-SAT `maximize` objective; `daily_balance` additionally introduces one auxiliary overage integer variable per distinct day.

## Task decomposition

`decompose_minutes(total, preferred, maximum)` splits a task's remaining minutes into fragments sized at `min(preferred, maximum)` -- in practice always `preferred`, since `SchedulingPreference` already enforces `preferred <= maximum`. A short trailing remainder (under one 15-minute slot) merges into the previous fragment rather than becoming its own awkward micro-session. `maximum_session_minutes` therefore acts as a validated ceiling on `preferred`, not as an active decomposition target -- see the comment on `test_decomposition_never_exceeds_preferred_or_maximum` in `tests/test_scheduling.py`. Each fragment then gets its own set of start-time candidates for CP-SAT to choose among.

## Infeasibility

If a task cannot be fully scheduled, the solver does not fail silently. `SchedulingResult.metrics` reports `tasks_fully_scheduled`, `tasks_partially_scheduled`, and total `unscheduled_minutes`; `SchedulingResult.conflicts` lists a `SchedulingConflict` per affected task with a human-readable reason and its own `unscheduled_minutes`; `unscheduled_minutes_by_task` gives the same breakdown by task id. `SchedulingResult.status` is `INFEASIBLE` whenever any task has unscheduled minutes and no session was produced for it at all (see `_result`'s `final_status` computation) -- a partially-schedulable set of tasks still reports `OPTIMAL`/`FEASIBLE` with non-zero `unscheduled_minutes`, so the caller can tell "some work didn't fit" apart from "nothing could be scheduled."

## Locked sessions and regeneration

A locked `StudySession` is carried into every subsequent `solve()` call via `SchedulingProblem.locked_sessions`. It is (a) treated as busy time other sessions can't overlap, (b) excluded from the per-task remaining-minutes requirement, and (c) always included unmodified in the output. `StudySchedulingService.regenerate_remaining` is exactly `solve()` with an updated `locked_sessions` set -- there is no separate "regeneration" algorithm, which is what guarantees a locked decision is never silently discarded.

## Timezones

Every scheduling type requires timezone-aware datetimes and rejects naive ones at construction. Study-hour clipping and daily-balance day-grouping both convert to the student's `SchedulingPreference.timezone` before comparing against local times, then convert back to the original timestamp's timezone for the actual window bounds -- see `_clip_to_study_windows` and `_local_day`. `tests/test_scheduling.py::test_dst_boundary_uses_timezone_aware_offsets` and `test_cross_midnight_window_is_clipped_to_daily_study_hours` exercise the two places this has historically gone wrong (DST transitions, and a calendar window that spans midnight).
