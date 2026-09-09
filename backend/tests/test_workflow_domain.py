from datetime import UTC, datetime

import pytest

from app.domain.enums import WorkflowStatus as S
from app.domain.errors import InvalidWorkflowTransition
from app.domain.workflows import TERMINAL_STATES, TRANSITIONS, transition


@pytest.mark.parametrize(
    "source,target", [(s, t) for s, targets in TRANSITIONS.items() for t in targets]
)
def test_valid_transitions(source: S, target: S) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = transition(source, target, None, now)
    assert result.current == target
    assert result.updated_at == now
    assert result.started_at == (now if target == S.ANALYZING else None)
    assert result.completed_at == (now if target in TERMINAL_STATES else None)


@pytest.mark.parametrize(
    "source,target", [(s, t) for s in S for t in S if t not in TRANSITIONS.get(s, ())]
)
def test_invalid_transitions(source: S, target: S) -> None:
    with pytest.raises(InvalidWorkflowTransition):
        transition(source, target, None)


def test_started_time_is_preserved() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    assert transition(S.ANALYZING, S.PLAN_READY, started).started_at == started
