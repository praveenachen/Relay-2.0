import re
from datetime import date, timedelta

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_IN_N_DAYS = re.compile(r"^in (\d+) days?$")


def resolve_relative_date(phrase: str | None, meeting_date: date) -> date | None:
    """Deterministic, not AI: the model extracts the raw phrase (never a
    date), and only this function decides an actual calendar date from it,
    relative to when the meeting happened. Returns None for anything it
    cannot confidently resolve -- the raw phrase is preserved either way,
    and an unresolved date requires the student's review rather than a
    guess (see docs/workflows/collaborate.md)."""
    if not phrase:
        return None
    text = phrase.strip().lower()
    if text == "today":
        return meeting_date
    if text == "tomorrow":
        return meeting_date + timedelta(days=1)
    if text in ("next week", "in a week"):
        return meeting_date + timedelta(days=7)
    match = _IN_N_DAYS.match(text)
    if match:
        return meeting_date + timedelta(days=int(match.group(1)))
    prefix_next = text.startswith("next ")
    weekday_name = text[len("next ") :] if prefix_next else text
    if weekday_name in _WEEKDAYS:
        target = _WEEKDAYS[weekday_name]
        delta = (target - meeting_date.weekday()) % 7
        # "next Thursday" said on a Thursday means a week out, not today;
        # otherwise "next X" and plain "X" both mean this cycle's X.
        if prefix_next and delta == 0:
            delta = 7
        return meeting_date + timedelta(days=delta)
    return None
