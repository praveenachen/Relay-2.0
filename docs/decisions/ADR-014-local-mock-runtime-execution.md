# ADR-014-local-mock-runtime-execution

Status: Accepted for Phase 4

# Context

Phase 4 needs to prove the path from approval to an external artifact record, but real Notion OAuth and Agent Runtime workers are out of scope.

# Decision

Implement `LocalRuntimeClient` as an in-process adapter for the existing `RuntimeClient` protocol. It accepts only the approved `create_notion_study_page` payload, calls `MockNotionConnector`, persists a local execution snapshot, and records a simulated external artifact.

# Rationale

This exercises the same boundary shape that Agent Runtime will eventually use: operation, payload, idempotency key, snapshot, result, and error code. It also keeps the user-facing workflow honest because approval leads to a visible artifact without pretending that a real Notion account was modified.

# Consequences

Local execution is synchronous and has no queue, retry worker, cancellation semantics, or remote telemetry. Simulated artifacts have `connected_account_id = NULL`. A real connector must bind an owned destination account before live writes are allowed.
