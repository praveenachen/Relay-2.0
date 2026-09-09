from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from app.domain.enums import WorkflowStatus as S
from app.domain.errors import InvalidWorkflowTransition

TRANSITIONS = MappingProxyType(
    {
        S.DRAFT: frozenset({S.ANALYZING, S.CANCELLED}),
        S.ANALYZING: frozenset({S.PLAN_READY, S.FAILED, S.CANCELLED}),
        S.PLAN_READY: frozenset({S.AWAITING_APPROVAL, S.CANCELLED}),
        S.AWAITING_APPROVAL: frozenset({S.APPROVED, S.REJECTED, S.CANCELLED}),
        S.APPROVED: frozenset({S.QUEUED, S.CANCELLED}),
        S.QUEUED: frozenset({S.EXECUTING, S.CANCELLED, S.FAILED}),
        S.EXECUTING: frozenset({S.COMPLETED, S.PARTIALLY_COMPLETED, S.FAILED}),
    }
)
TERMINAL_STATES = frozenset({S.COMPLETED, S.PARTIALLY_COMPLETED, S.FAILED, S.REJECTED, S.CANCELLED})


@dataclass(frozen=True)
class Transition:
    previous: S
    current: S
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def transition(
    current: S, target: S, started_at: datetime | None, now: datetime | None = None
) -> Transition:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise InvalidWorkflowTransition()
    instant = now or datetime.now(UTC)
    return Transition(
        current,
        target,
        instant,
        instant if target == S.ANALYZING else started_at,
        instant if target in TERMINAL_STATES else None,
    )
