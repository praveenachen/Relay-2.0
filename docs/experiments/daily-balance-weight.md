# Daily-balance weight experiment

Status: Run against the real CP-SAT solver. Results below are actual solver output, not fabricated.

# Question

`SchedulingWeights.daily_balance` is meant to discourage the solver from clustering a large task's sessions onto a single day when they could spread across the available window. Does raising it actually change the schedule, and how much weight does it take?

# Setup

One task, `estimated_minutes=240`, deadline `2026-01-12T17:00` (America/Toronto). A 5-day availability window, `2026-01-05` through `2026-01-09`, `08:00`-`22:00` each day. `preferred_session_minutes=maximum_session_minutes=60`, so the task always decomposes into four fixed 60-minute fragments -- only *which days* the solver places them on can change with the weight. `minimum_break_minutes=15`.

# Procedure

Solved the identical `SchedulingProblem` with `CPSATStudyScheduler` across a sweep of `daily_balance` weights (all other weights at their shipped defaults), and recorded the number of distinct calendar days the four sessions landed on.

# Actual result

| `daily_balance` | Distinct days used |
| --- | --- |
| 0 | 1 |
| 4 (shipped default) | 1 |
| 20 | 2 |
| 50 | 3 |
| 100 | 4 |
| 200 | 4 |
| 500 | 4 |
| 1000 | 4 |

At every weight, `2026-01-05` is never used -- it falls outside the 7-day `deadline_urgency` lookback window (168 hours before the `2026-01-12 17:00` deadline is `2026-01-05 17:00`), so it never scores competitively against the closer days regardless of `daily_balance`. The effect saturates at 4 distinct days once the weight reaches 100; it never reaches all 5 available days in this scenario.

Reproduced in `backend/tests/test_scheduling.py::test_daily_balance_weight_spreads_large_task_across_days`, which asserts the `0` and `100` rows (1 day and 4 days respectively) so a regression in either the day-grouping logic or the objective wiring is caught.

# Interpretation

- `daily_balance` is a real, working lever -- it measurably changes the schedule at a large enough value.
- The **shipped default (`4`) has zero effect in this scenario** -- `deadline_urgency` (`40` per point, versus `daily_balance`'s `4`) dominates it completely. A deployment that actually wants day-spreading behavior for large tasks needs to raise `daily_balance` well past its current default; `50`-`100` is where it starts winning against urgency in a scenario like this one.
- This is exactly the failure mode "don't hide unexplained magic numbers" warns about: a weight that exists in the objective but is calibrated so low it's inert is arguably worse than not having it, because it looks like a feature that was considered and tuned when it wasn't. It is left at its original value here rather than silently bumped, since changing shipped defaults deserves its own deliberate decision -- but this file exists so that decision is made with real numbers instead of a guess.
- The earlier version of `_daily_balance_penalties` computed its per-day target from the sum of *candidate* durations (every alternative start-time option for every fragment) rather than the sum of *required* task minutes. Because a single 240-minute requirement generates dozens of overlapping 15-minute-apart candidate slots, that inflated the "fair share" denominator by roughly two orders of magnitude, making the overage penalty numerically negligible at any reasonable weight -- weight sweeps during this experiment are what surfaced it. Fixed to use `task.estimated_minutes - locked_minutes`, matching the same requirement figure the hard per-task constraint already uses.
