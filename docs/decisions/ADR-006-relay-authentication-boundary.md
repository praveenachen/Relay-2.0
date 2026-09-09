# ADR-006-relay-authentication-boundary

Status: Accepted for Phases 1 and 2

# Context

Relay needs real user identity without coupling login to Notion, Google, or GitHub connections.

# Options Considered

Managed hosted identity; Next.js-owned identity plus cross-service tokens; FastAPI Users with database cookie sessions.

# Decision

Use FastAPI Users, Argon2 via pwdlib, and revocable database sessions. Proxy browser API requests through Next.js and authorize again in FastAPI.

# Rationale

This works locally without vendor setup and delegates hashing/token lifecycle to a mature library. Opaque sessions support logout revocation.

# Consequences

Strict Origin checks protect cookie writes. Secure cookies require HTTPS outside local development. FastAPI Users is in maintenance mode; email verification, recovery, rate limiting, and expiry cleanup remain production work.

# When We Would Reconsider

Reconsider for institutional SSO, MFA, hosted identity requirements, or an unacceptable maintenance/security trajectory.
