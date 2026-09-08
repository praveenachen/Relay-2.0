# ADR-002-human-approval-before-side-effects

Status: Accepted for Phase 0

# Context

Probabilistic interpretation can produce incorrect actions in external student accounts.

# Options Considered

Autonomous execution; approval only for selected operations; explicit approval for meaningful external side effects.

# Decision

Require explicit approval of a versioned proposal before meaningful external side effects.

# Rationale

Students must be able to inspect destinations and exact changes. Deterministic validation and authorization remain required after approval.

# Consequences

Future services need immutable proposal versions, approval history, revalidation, and visible partial outcomes. Edits invalidate approval. No approval implementation exists in Phase 0.

# When We Would Reconsider

Consider narrowly scoped standing approvals only after real usage demonstrates need and explicit user-defined limits, revocation, and auditing are designed.
