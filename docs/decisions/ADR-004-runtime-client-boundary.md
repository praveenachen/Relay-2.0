# ADR-004-runtime-client-boundary

Status: Accepted for Phase 0

# Context

Application services must not depend on a particular executor transport or absorb reliability machinery.

# Options Considered

Direct HTTP calls in routes; an embedded worker implementation; a typed Protocol with adapters later.

# Decision

Define asynchronous submit_execution, get_execution, and cancel_execution methods using domain-neutral Pydantic request and result models.

# Rationale

A small port makes dependencies explicit and permits future LocalRuntimeClient and AgentRuntimeHttpClient adapters without changing student-domain rules.

# Consequences

The contract is still the Relay boundary for execution. It includes idempotency keys but provides no idempotency guarantee by itself. Phase 5 has an in-process `LocalRuntimeClient` for LEARN publishing; Agent Runtime transport, queues, retry workers, and cancellation remain future work.

# When We Would Reconsider

Revise the contract when Agent Runtime has a concrete authenticated API and error/cancellation semantics; avoid changing it based only on hypothetical features.
