# ADR-009-immutable-approved-action-payload

Status: Accepted for Phases 1 and 2

# Context

An interpretation or edited proposal may differ from the exact action the user reviewed.

# Options Considered

Regenerate at execution; store only an approval flag; persist an immutable approved payload snapshot.

# Decision

Persist the exact reviewed JSON payload at resolution, require it to match the original/current proposal, and disallow further resolution edits.

# Rationale

Authorization must bind to concrete content. Parent-run locking serializes competing decisions and audit events commit atomically.

# Consequences

Editing is not exposed yet. A rejected action rejects its run and expires pending siblings. Duplicate decisions return 409. Future execution must consume the approved snapshot, not regenerate it.

# When We Would Reconsider

Add versioned approval rounds only when editing/replanning is implemented with explicit invalidation, destination identity binding, and a reviewed migration.
