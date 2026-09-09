# ADR-028: Prefer partial completion over distributed rollback

## Context

During COLLABORATE execution, one approved action can succeed before another fails. Attempting to delete successful external work after a sibling failure would add new side effects, could fail itself, and may remove useful work the student already approved.

## Decision

Relay keeps successful external artifacts when sibling actions fail. The workflow becomes `PARTIALLY_COMPLETED` when at least one action succeeds and at least one fails.

## Rationale

Truthful state is safer than theatrical rollback. The approved action really happened, so Relay records it and reports the failed siblings separately. Per-action idempotency prevents retries from duplicating the successes.

## Consequences

Students may need to retry or manually complete failed sibling actions, but they do not lose successful Notion tasks, GitHub issues, or review requests. Audit events and `result_payload` carry succeeded, failed, and total counts.

## When We Would Reconsider

If Relay adds explicit compensating actions, they should be separately proposed and approved rather than hidden inside an automatic rollback path.
