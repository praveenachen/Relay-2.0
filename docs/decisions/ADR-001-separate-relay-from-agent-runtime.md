# ADR-001-separate-relay-from-agent-runtime

Status: Accepted for Phase 0

# Context

Relay needs domain-specific planning and a reliable executor without coupling the executor to students or provider concepts.

# Options Considered

A single application with embedded workers; a separate generic runtime; provider-specific microservices.

# Decision

Keep Relay and Agent Runtime in separate repositories with a typed port between them.

# Rationale

Domain rules evolve separately from queueing and failure handling. A generic runtime can support other applications.

# Consequences

Two systems eventually need coordinated contracts, deployment, and observability. Phase 0 introduces no runtime service.

# When We Would Reconsider

Reconsider deployment separation if operational cost outweighs demonstrated reuse; preserve logical boundaries even if deployment changes.
