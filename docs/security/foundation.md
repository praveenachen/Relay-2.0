# Security boundaries

Phases 1 and 2 add real Relay authentication, owner-scoped resources, explicit approval snapshots, audit history and encrypted connection persistence. See [authentication](authentication.md), [credential storage](credential-storage.md), and [external connections](external-connections.md) for implementation details and limitations.

Workflow inputs and future model output are untrusted data. Typed schemas and deterministic validation precede authorization. This phase accepts draft payloads but does not interpret instructions, upload files or execute actions. User-provided content never grants access to another user's resources.

Provider tokens do not appear in response schemas or audit metadata. Validation errors omit submitted inputs, and database/domain exceptions map to safe responses. Secret settings are redacted types and local env files are ignored. Deployment, log/backup access, rate limiting, email verification, recovery, retention and key rotation operations need further production work.
