# External connection boundary

Relay authentication and external provider authorization are independent. Users may finish onboarding with zero connected tools. OAuth interfaces model authorization URL creation, code exchange, refresh, and revocation, but no provider adapter exists yet.

Supported account providers are GOOGLE, NOTION and GITHUB. Proposed actions separately use GOOGLE_CALENDAR, NOTION and GITHUB. This distinction keeps Google account identity separate from a particular Google product's action vocabulary.

`ConnectionService` creates unique records, encrypts/replaces credentials, changes status, exposes safe metadata, and disconnects locally. Statuses are CONNECTED, EXPIRED, REVOKED and ERROR. Expiry status updates are available internally; no automatic refresh/expiry worker exists. All service mutations include owner checks and audit records.

| Endpoint | Current behavior |
| --- | --- |
| `GET /connections` | Safe metadata for current user's records |
| `GET /connections/{provider}` | List for this user's provider; empty if none |
| `DELETE /connections/{provider}` | Clear local credentials and revoke all this user's provider records |
| `GET /connections/{provider}/authorize` | Authenticated 501 OAUTH_NOT_CONFIGURED |
| `GET /connections/{provider}/callback` | Authenticated 501 OAUTH_NOT_CONFIGURED; no code exchange |

An already revoked connection can be disconnected again without duplicating the audit event. A provider with no owned record returns 404. The frontend displays actual metadata and a clear not-yet-available response when Connect is attempted. It never fabricates a connected account.

Before enabling real OAuth, implement short-lived single-use state bound to the authenticated session, PKCE when supported, allowlisted redirect URIs, least-privilege scopes, provider response validation, refresh-token rotation, revocation handling, and remote disconnect semantics. Keep these in provider adapters/application services rather than route handlers. Callback parameters currently have no effect and do not grant access.
