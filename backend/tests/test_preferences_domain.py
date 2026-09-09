from datetime import time

import pytest

from app.domain.errors import InvalidPreferenceConfiguration
from app.domain.preferences import validate_preferences


def test_valid_preferences() -> None:
    validate_preferences("America/Toronto", time(8), time(22), 50, 90, 10)


@pytest.mark.parametrize(
    "timezone,start,end,preferred,maximum,pause",
    [
        ("Invalid/Zone", 8, 22, 50, 90, 10),
        ("UTC", 8, 8, 50, 90, 10),
        ("UTC", 22, 8, 50, 90, 10),
        ("UTC", 8, 22, 100, 90, 10),
        ("UTC", 8, 22, 50, 90, -1),
        ("UTC", 8, 22, 0, 90, 10),
    ],
)
def test_invalid_preferences(
    timezone: str, start: int, end: int, preferred: int, maximum: int, pause: int
) -> None:
    with pytest.raises(InvalidPreferenceConfiguration):
        validate_preferences(timezone, time(start), time(end), preferred, maximum, pause)
