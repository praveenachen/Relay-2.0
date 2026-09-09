# ADR-018-provider-specific-token-lifecycle

Status: Accepted for Phase 5

# Context

Relay will eventually support Notion, Google Calendar, and GitHub. Their OAuth/token semantics are not identical.

# Decision

Keep `ConnectedAccount` generic enough for shared metadata, status, encrypted access token, optional refresh token, optional expiry, and provider metadata. Do not force every provider into refresh-token behavior.

# Consequences

Provider services own token lifecycle details. Notion can store nullable refresh/expiry fields while Google Calendar can later require refresh handling. This avoids a brittle "one OAuth abstraction fits all providers" design.
