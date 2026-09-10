# Workflow state machine

`app/domain/workflows.py` is the single transition table. There is no endpoint that accepts an arbitrary workflow status. `POST /workflow-runs` creates DRAFT only. Planning/execution transitions are internal service methods, driven by each workflow's own service (`app/workflows/lecture_notes/`, `app/workflows/study_plan/`) through their public API routes -- not by any endpoint that sets status directly.

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> ANALYZING
    DRAFT --> CANCELLED
    ANALYZING --> PLAN_READY
    ANALYZING --> FAILED
    ANALYZING --> CANCELLED
    PLAN_READY --> AWAITING_APPROVAL
    PLAN_READY --> CANCELLED
    AWAITING_APPROVAL --> APPROVED
    AWAITING_APPROVAL --> REJECTED
    AWAITING_APPROVAL --> CANCELLED
    APPROVED --> QUEUED
    APPROVED --> CANCELLED
    QUEUED --> EXECUTING
    QUEUED --> CANCELLED
    QUEUED --> FAILED
    EXECUTING --> COMPLETED
    EXECUTING --> PARTIALLY_COMPLETED
    EXECUTING --> FAILED
```

COMPLETED, PARTIALLY_COMPLETED, FAILED, REJECTED, and CANCELLED are terminal. Self-transitions and terminal-state exits fail with `InvalidWorkflowTransition`. Recoverable runtime submission failures can leave a run in QUEUED or EXECUTING with a retryable error code; retrying reuses the approved payload and idempotency key. Terminal states still do not reopen.

`WorkflowService.transition_workflow` verifies ownership, locks the run, applies the pure transition decision, persists timestamps, appends WORKFLOW_STATE_CHANGED, and commits atomically. `started_at` marks entry into ANALYZING; `completed_at` marks any terminal outcome; `updated_at` changes on every accepted transition. Internal composition uses `apply_transition` within a locked transaction.

## Approval gates

Entering AWAITING_APPROVAL requires a non-empty action set with pending requests. Every action must have an approved request before APPROVED or QUEUED. LEARN, PLAN, and COLLABORATE expose workflow-specific endpoints that create proposed actions and drive approved execution (`/workflows/learn/{id}/execute`, `/workflows/plan/{id}/execute`, `/workflows/collaborate/{id}/execute`).

Request creation deep-copies the proposed payload. Approval requires PENDING, ownership, AWAITING_APPROVAL, and an exact JSON payload match against both the stored original and current action. Object key order is ignored; JSON scalar types, array order, and values are retained. Payload editing is deliberately not exposed. A changed proposal fails with a conflict instead of silently authorizing different work.

The exact approved snapshot is persisted and cannot be changed through supported APIs/ORM writes after resolution. Future executors must use this snapshot. Approving all actions moves the run to APPROVED but does not submit execution. Rejecting one action rejects the run and expires other pending requests. Duplicate approve/reject requests return 409, including concurrent resolutions serialized with a PostgreSQL parent-run lock. No second decision event is appended.

QUEUED and EXECUTING are real, exercised states for both LEARN (Notion) and PLAN (Google Calendar) execution. PARTIALLY_COMPLETED is used by PLAN when some but not all approved calendar blocks could be created (see `docs/architecture/plan-sequence.md`); LEARN's single-action executions only ever reach COMPLETED or FAILED. Cancellation is best effort through the runtime boundary; completed external side effects are recorded rather than rolled back.
