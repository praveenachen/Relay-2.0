# ADR-015-notion-oauth-for-user-workspace-access

Status: Accepted for Phase 5

# Context

LEARN needs to publish to a student's own Notion workspace. A shared developer token would collapse user identity, page access, and revocation into one unsafe credential.

# Decision

Use Notion public OAuth per Relay user. Store hashed single-use state during authorization, exchange codes server-side, encrypt access tokens, and persist safe workspace metadata in `ConnectedAccount`.

# Consequences

Local development requires Notion integration configuration and a Fernet key before real publishing. Google Calendar and GitHub remain placeholders.
