from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulingWeights:
    unscheduled_minute: int = 1000
    deadline_urgency: int = 40
    priority: int = 30
    preferred_period: int = 12
    fragmentation: int = 8
    daily_balance: int = 4


DEFAULT_WEIGHTS = SchedulingWeights()
