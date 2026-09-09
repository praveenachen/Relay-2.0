# ADR-021-normalize-external-calendar-data

Status: Accepted for Phase 6

# Context

Google Calendar's event JSON has provider-specific shapes (timed events use `dateTime`, all-day events use a bare `date`; busy intervals arrive as full event objects with fields the scheduler doesn't need) that the scheduling engine must never depend on, per its own constraint against operating on raw provider objects.

# Decision

`app/connectors/google/mapper.py` is the single boundary that turns a raw Google Calendar event into Relay's own `BusyInterval`. `parse_google_datetime` handles both `dateTime` (parsed and required to carry an offset) and bare `date` (treated as UTC midnight, since Relay has no reliable timezone for an all-day event and refusing to schedule around it entirely would be worse than an approximate boundary). Nothing past `busy_interval_from_event` ever sees a Google-shaped dict.

# Rationale

Every other option (letting the scheduler branch on provider-specific keys, or crashing on the case the original implementation didn't handle) either violates the scheduling engine's own architectural boundary or produces a support incident the first time a student's calendar contains an all-day event -- which is common (all-day "no class" or vacation blocks). A single, tested normalization function is cheaper to get right once than to re-derive at every call site.

# Consequences

`tests/test_plan_connectors.py::test_all_day_busy_event_is_treated_as_utc_midnight` locks in the all-day behavior. If a student's actual local timezone differs meaningfully from UTC for an all-day event's boundary, the busy interval may be off by up to that offset -- acceptable for a "don't double-book" hard constraint (it only makes Relay slightly more conservative about availability near an all-day event's edges, never less), tracked as a known limitation in `docs/workflows/plan.md`.

# When We Would Reconsider

If all-day-event precision becomes a real complaint (e.g., a student's morning-only all-day block is treated as blocking the whole day when it shouldn't be), revisit using the calendar's own `time_zone` metadata (already normalized into `CalendarListItem.time_zone`) to anchor the all-day boundary instead of UTC.
