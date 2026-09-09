from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.errors import InvalidPreferenceConfiguration


def validate_preferences(
    timezone: str, earliest: time, latest: time, preferred: int, maximum: int, minimum_break: int
) -> None:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidPreferenceConfiguration() from None
    if (
        earliest >= latest
        or earliest.tzinfo is not None
        or latest.tzinfo is not None
        or not 5 <= preferred <= maximum <= 480
        or not 0 <= minimum_break <= 240
    ):
        raise InvalidPreferenceConfiguration()
