# ADR-008-connected-account-abstraction

Status: Accepted for Phases 1 and 2

# Context

Provider accounts have independent identity, credentials, scopes, and lifecycle even while OAuth is unavailable.

# Options Considered

Embed tokens in users; use provider SDKs in route handlers; a separate connected-account service and OAuth port.

# Decision

Persist ConnectedAccount separately, scoped by owner/provider/external identity, and expose safe metadata. Leave authorize/callback as authenticated 501 responses.

# Rationale

Users can onboard independently of integrations and provider SDK choices can be postponed honestly.

# Consequences

Multiple accounts per provider are modeled; provider-level disconnect affects all owned records. Remote revocation and refresh require future adapters.

# When We Would Reconsider

Revise endpoint granularity when users need per-account management or provider-specific scope selection.
