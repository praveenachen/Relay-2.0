"""Conservative, literal-date extraction used to guard against invented due dates.

Only recognizes dates that are written explicitly in the source text (ISO
`YYYY-MM-DD` or `Month Day[, Year]`). Never derives a date by offsetting from
another event (e.g. "before Demo Day on Oct 3" must not resolve to Oct 2).
"""

import re
from datetime import UTC, datetime

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(
    rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)


def extract_literal_dates(text: str) -> set[tuple[int, int, int | None]]:
    """Return (month, day, year|None) tuples for dates written explicitly in `text`."""
    found: set[tuple[int, int, int | None]] = set()
    for match in _ISO_DATE.finditer(text):
        year, month, day = (int(part) for part in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            found.add((month, day, year))
    for match in _MONTH_DAY.finditer(text):
        month_number = _MONTHS.get(match.group(1).lower())
        if month_number is None:
            continue
        day_number = int(match.group(2))
        year_number = int(match.group(3)) if match.group(3) else None
        if 1 <= day_number <= 31:
            found.add((month_number, day_number, year_number))
    return found


def date_is_literally_supported(content: str, due: datetime) -> bool:
    """Whether `due`'s calendar date is written explicitly somewhere in `content`."""
    for month, day, year in extract_literal_dates(content):
        if month == due.month and day == due.day and (year is None or year == due.year):
            return True
    return False


def first_literal_date(text: str, *, default_year: int | None = None) -> datetime | None:
    """The first explicit date found in `text`, or None. Never infers a relative offset."""
    dates = sorted(extract_literal_dates(text))
    if not dates:
        return None
    month, day, year = dates[0]
    year = year or default_year or datetime.now(UTC).year
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None
