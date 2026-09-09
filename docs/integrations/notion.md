# Notion integration

Relay supports Notion as the first real external destination for LEARN. The integration is public OAuth, per user, and least-privilege by page access. Relay does not use a shared developer token.

## Local configuration

Create a public Notion integration and configure the local redirect URL:

```text
http://localhost:8000/connections/NOTION/callback
```

Set these server-side values in `.env`:

```text
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
NOTION_REDIRECT_URI=http://localhost:8000/connections/NOTION/callback
NOTION_PUBLISH_MODE=real
TOKEN_ENCRYPTION_KEY=
```

`FRONTEND_ORIGIN` should point at the UI, usually `http://localhost:3000`. The frontend never receives tokens or client secrets.

## OAuth flow

`GET /connections/NOTION/authorize` creates a random state, stores only its SHA-256 hash with an expiry, and returns a Notion authorization URL. The callback validates state, handles provider errors, exchanges the code with Basic client authentication, encrypts the access token, and persists safe workspace metadata on `ConnectedAccount`.

Notion returns workspace/bot metadata with the token response. Relay records workspace id/name, workspace icon, bot id, and owner metadata where available. Access tokens are encrypted. Refresh tokens and expiry remain optional because Notion's token lifecycle should not be forced into the same shape as Google Calendar or GitHub.

## Destination discovery

Relay discovers accessible pages through Notion search and follows pagination until no `next_cursor` remains. Provider responses are normalized to:

```python
NotionDestination(id: str, title: str, icon_url: str | None)
```

Users choose a default lecture-notes destination on `/connections`. LEARN stores the selected connection and destination inside the proposed action before approval, so execution uses the exact approved payload.

## Publishing

The execution path remains:

```text
ApprovalRequest.approved_payload
RuntimeClient.submit_execution()
LocalRuntimeClient
DatabaseNotionConnector
RealNotionConnector
Notion API
```

The LLM never generates Notion blocks. `NotionStudyPageMapper` deterministically maps `LectureSummary` into Notion blocks, omits empty optional sections, splits long rich text, and falls back to readable text when formulas should not be sent as equations.

## Idempotency

Notion page creation does not expose a native idempotency key. Relay uses application-level idempotency by checking `ExternalArtifact.idempotency_key` before publishing and storing the key with the created artifact. The real connector also places a small Relay action marker at the top of the page content.

This prevents duplicates after Relay has recorded the artifact. It does not prove exactly-once behavior for an ambiguous network timeout after Notion receives the request but before Relay receives or stores the response. In that case Relay surfaces a typed timeout failure and does not claim that no page exists.

## Errors

Raw provider errors are translated to Relay domain errors:

- `NOTION_NOT_CONNECTED`
- `NOTION_AUTHORIZATION_FAILED`
- `NOTION_PERMISSION_DENIED`
- `NOTION_DESTINATION_NOT_FOUND`
- `NOTION_RATE_LIMITED`
- `NOTION_VALIDATION_FAILED`
- `NOTION_UNAVAILABLE`
- `NOTION_REQUEST_TIMEOUT`
- `NOTION_PUBLISH_FAILED`

401 during publishing marks the connection revoked and clears stored tokens. Audit metadata contains ids and status codes only where useful; it does not contain OAuth codes, access tokens, client secrets, or lecture bodies.

## Testing

Normal tests use `MockNotionConnector` or HTTP/test doubles. CI does not require a live Notion account. The test suite covers OAuth state validation, encrypted token persistence, token leakage prevention, destination pagination/selection, deterministic block mapping, real publish through a mocked Notion API boundary, provider failures, and idempotent duplicate execution.
