# ADR-027: Execute COLLABORATE provider actions independently

## Context

A single meeting can produce several approved actions across Notion and GitHub. Neither provider participates in a shared transaction, and external APIs can fail independently after earlier sibling actions succeed.

## Decision

`CollaborateExecutionService` submits each approved `ProposedAction` to `RuntimeClient` independently with its own idempotency key. Each successful provider result is persisted as an `ExternalArtifact` before the service moves to the next action.

## Rationale

Independent execution reflects the real failure model. A Notion task and a GitHub issue are separate side effects, so Relay should not pretend it can atomically commit or roll back both. Per-action execution also lets retries skip already-recorded artifacts without duplicating external work.

## Consequences

A run can end `COMPLETED`, `PARTIALLY_COMPLETED`, or `FAILED` depending on how many approved actions succeeded. The UI and history show the aggregate result, while artifact records preserve exactly which external work exists.

## When We Would Reconsider

If a future provider supports native transactional batches for a single destination, Relay could use that inside one connector. Cross-provider distributed transactions should still be avoided.
