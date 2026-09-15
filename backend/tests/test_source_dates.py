from datetime import UTC, datetime

from app.sources.dates import date_is_literally_supported, first_literal_date


def test_extracts_explicit_iso_date():
    due = first_literal_date("Deliverable due 2026-09-30")
    assert due == datetime(2026, 9, 30, tzinfo=UTC)


def test_extracts_explicit_month_name_date():
    due = first_literal_date("Please freeze by Sep 30, 2026")
    assert due == datetime(2026, 9, 30, tzinfo=UTC)


def test_does_not_extract_a_date_from_vague_timing():
    assert first_literal_date("Let's do this when you have time") is None
    assert first_literal_date("Finish this before the client review") is None


def test_supported_date_matches_literal_text():
    content = "We need to freeze scope by Sep 30 at the latest."
    assert date_is_literally_supported(content, datetime(2026, 9, 30, tzinfo=UTC))


def test_unsupported_date_is_rejected_even_if_plausible():
    # The source only ever mentions Oct 3 ("Demo Day"); a due_date of Oct 2
    # (e.g. an invented "day before" inference) is not literally supported.
    content = "Finish the deck before Demo Day on Oct 3."
    assert not date_is_literally_supported(content, datetime(2026, 10, 2, tzinfo=UTC))
    assert date_is_literally_supported(content, datetime(2026, 10, 3, tzinfo=UTC))


def test_no_dates_in_content_means_nothing_is_supported():
    assert not date_is_literally_supported(
        "Get to this when you have time.", datetime(2026, 10, 2, tzinfo=UTC)
    )
