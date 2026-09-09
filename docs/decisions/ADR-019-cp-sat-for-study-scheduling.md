# ADR-019-cp-sat-for-study-scheduling

Status: Accepted for Phase 6

# Context

PLAN must turn a set of academic tasks, deadlines, and calendar availability into concrete study session times. The project's stated architectural principle is that AI may interpret information but must never choose the actual calendar slots.

# Options Considered

An LLM proposes session times directly; a greedy first-fit heuristic; a constraint solver (CP-SAT) that treats scheduling as an optimization problem over a bounded candidate set.

# Decision

Use Google OR-Tools CP-SAT (`app/scheduling/solver.py::CPSATStudyScheduler`) as the only component that selects which candidate time slots become study sessions. Hard rules (no overlap, no work past a deadline, study-hour and break enforcement, locked sessions staying fixed) are modeled as CP-SAT constraints; preferences (urgency, priority, time-of-day, fragmentation, daily balance) are a single linear objective built from centralized weights (`app/scheduling/objectives.py`).

# Rationale

CP-SAT gives a reproducible, explainable answer: the same `SchedulingProblem` always produces the same `SchedulingResult`, every hard rule is provably respected or the solver reports infeasibility, and every soft preference is a named, inspectable weight rather than opaque model behavior. An LLM scheduling directly could not offer any of these guarantees, and a plain greedy heuristic cannot express competing soft preferences (urgency vs. daily balance) as a genuine trade-off the way an objective function can.

# Consequences

The scheduling package cannot import FastAPI, the Notion/Google SDKs, or an LLM client -- it only accepts Relay's own typed domain models. Every input (tasks, availability, busy intervals, preferences) must be normalized into those types before reaching the solver; see ADR-020 for the hard/soft split and ADR-021 for calendar normalization specifically. Soft-preference weights are not empirically tuned (see `docs/experiments/daily-balance-weight.md`); they are a heuristic starting point subject to revision once real usage data exists.

# When We Would Reconsider

If the candidate-slot search space grows large enough that CP-SAT's `MAX_SOLVER_SECONDS` budget becomes a real constraint (e.g., many tasks over a long horizon with fine-grained slots), consider a coarser slot granularity or a two-stage solve (day assignment, then within-day placement) before reconsidering the solver technology itself.
