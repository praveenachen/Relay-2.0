# Google Calendar integration

Relay supports Google Calendar as the destination for PLAN's approved study blocks and as the source of a student's existing commitments. Like Notion, this is public per-user OAuth -- Relay never uses a shared developer token, and never requests Gmail access.

## Local configuration

Create an OAuth 2.0 client (Web application) in Google Cloud Console and configure the local redirect URL:

```text
http://localhost:8000/connections/GOOGLE/callback
```

Set these server-side values in `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/connections/GOOGLE/callback
TOKEN_ENCRYPTION_KEY=
```

## Scopes

Relay requests exactly:

```text
https://www.googleapis.com/auth/calendar.events
https://www.googleapis.com/auth/calendar.readonly
```

plus `openid email profile` to identify the account. `tests/test_plan_connectors.py::test_google_oauth_url_uses_calendar_scopes_only` asserts the authorization URL never contains a Gmail scope. This is the project's least-privilege boundary: Relay can read a student's calendar and create/read the study events it manages; it cannot read or send mail, and (unlike the events scope, which is per-event) it cannot see other event details as anything more than a busy/free interval unless Relay itself created the event.

## OAuth flow

`GET /connections/GOOGLE/authorize` creates a random state, stores only its SHA-256 hash with an expiry, and returns a Google authorization URL with `access_type=offline&prompt=consent` (required to reliably receive a refresh token). The callback validates state, exchanges the code, fetches basic profile info, encrypts both the access and refresh token, and persists them on `ConnectedAccount`.

## Token refresh

Google access tokens expire (Notion's do not, which is why `ADR-018-provider-specific-token-lifecycle.md` explicitly left refresh handling to each provider rather than forcing a shared abstraction). `GoogleCalendarService.connection()` is the one place that checks `token_expires_at` before returning a usable connection: if expired and a refresh token exists, it calls `GoogleOAuthClient.refresh()`, re-encrypts the new access token, and updates the expiry; if refresh fails or no refresh token is stored, the connection is marked `EXPIRED` and the student needs to reconnect. This governs the read paths (calendar listing, availability retrieval). The direct database connector used at *execution* time (`DatabaseGoogleCalendarConnector`, inside `LocalRuntimeClient`) does not itself attempt a refresh -- see the "Known limitations" note in `docs/workflows/plan.md`.

## Calendar selection

A student can have events across several calendars; Relay does not assume the primary one is correct for study blocks. `GoogleCalendarService.refresh()`/`list()` persist and read `GoogleCalendarRecord` rows per connection; `select()` marks one as the default and stores its id/summary on `ConnectedAccount.provider_metadata` for quick lookup without a join.

## Availability normalization

`GoogleCalendarApiClient.busy_intervals` reads `/calendars/{id}/events` for the planning window and maps every item through `busy_interval_from_event` into Relay's own `BusyInterval`. An all-day event reports a bare `date` instead of `dateTime`; `parse_google_datetime` treats that as UTC midnight rather than raising and losing the whole availability fetch over one all-day event (see `tests/test_plan_connectors.py::test_all_day_busy_event_is_treated_as_utc_midnight`). The scheduling engine never sees the raw Google JSON.

## Event creation and idempotency

`CreateCalendarStudyBlockAction` is the typed action the approval flow freezes -- never a raw dict. `GoogleCalendarApiClient.create_event` embeds the Relay idempotency key in both the event description and `extendedProperties.private.relay_idempotency_key`, for operator visibility on the Google side; the actual duplicate-prevention guarantee is Relay's own `ExternalArtifact.idempotency_key` uniqueness constraint, checked before creating each block (see `docs/architecture/plan-sequence.md`).

## Errors

Raw HTTP responses are translated to Relay domain errors:

- `GOOGLE_NOT_CONNECTED`
- `GOOGLE_AUTHORIZATION_FAILED` (401, or a failed/absent refresh)
- `GOOGLE_PERMISSION_DENIED` (403)
- `CALENDAR_NOT_FOUND` (404)
- `CALENDAR_CONFLICT` (409)
- `CALENDAR_RATE_LIMITED` (429)
- `CALENDAR_REQUEST_TIMEOUT`
- `CALENDAR_UNAVAILABLE` (other 4xx/5xx or a network error)

A 401 while creating an event marks the connection revoked and clears stored tokens, the same pattern as the Notion connector.

## Testing

`tests/test_plan_connectors.py` covers OAuth scope/state, encrypted token persistence, HTTP status mapping (403, 429, timeout), calendar listing/selection, all-day event normalization, and both the successful and failed-refresh token lifecycle paths, all against `httpx.MockTransport` or monkeypatched clients -- no live Google API calls in CI.
