# ADR-020-hard-vs-soft-scheduling-constraints

Status: Accepted for Phase 6

# Context

A study schedule has rules that must never be broken (a session cannot overlap an existing calendar event) and preferences that should generally be honored but can trade off against each other (prefer mornings, but not at the cost of missing a deadline).

# Options Considered

Encode everything as objective weights (a large enough penalty simulates a hard rule); encode everything as CP-SAT constraints (reject preferences the solver can't fully satisfy instead of relaxing them); keep the two mechanisms structurally distinct.

# Decision

Hard rules are CP-SAT `model.add(...)` constraints; nothing about them is negotiable by weight. Soft preferences are terms in a single linear `maximize` objective (`app/scheduling/solver.py`, weighted by `app/scheduling/objectives.py::SchedulingWeights`). The two are never merged: a hard rule is never expressed as "a very large penalty," and a preference is never expressed as a constraint the solver can fail to satisfy.

Hard, as constraints:
- no overlap between any two selected sessions (including the minimum break)
- no session after a task's deadline
- sessions only inside permitted study hours (and only on allowed weekdays)
- no overlap with existing calendar busy intervals
- locked sessions stay fixed and reduce a task's remaining requirement
- total scheduled minutes per task never exceed what's required

Soft, as objective terms: deadline urgency, priority, preferred time of day, fragmentation, daily balance (see `docs/architecture/scheduling-engine.md` for the full table).

# Rationale

Simulating a hard rule with a large penalty is fragile: get the constant wrong (relative to other weights, or as the problem scales) and the "hard" rule can be violated to satisfy a soft one, silently. Keeping hard rules as actual constraints means CP-SAT reports `INFEASIBLE` rather than producing a schedule that quietly breaks a deadline. Keeping preferences soft means the solver always returns *a* schedule when a feasible one exists, even if not every preference is perfectly satisfied.

# Consequences

When no feasible schedule exists at all for a task's required minutes, the solver returns `SchedulingStatus.INFEASIBLE` with `SchedulingConflict`s naming the affected task and its unscheduled minutes, rather than forcing an approximate answer that violates a hard rule. Adding a new rule requires deciding, explicitly, which category it belongs to.

# When We Would Reconsider

If a future requirement needs a "soft hard constraint" (e.g., a deadline that can be missed with an explicit warning, at the student's choice), model it as an opt-in relaxation the student explicitly requests per task, not as a blurring of this boundary.
