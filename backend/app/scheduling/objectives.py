from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulingWeights:
    unscheduled_minute: int = 1000
    deadline_urgency: int = 40
    priority: int = 30
    preferred_period: int = 12
    fragmentation: int = 8
    # Scheduling sooner is only a tie-breaker. Completion, deadlines, and a
    # usable distribution across the week should decide the plan first.
    earliness: int = 1
    daily_balance: int = 8
    same_task_second_session: int = 250
    same_task_additional_session: int = 1500


DEFAULT_WEIGHTS = SchedulingWeights()
