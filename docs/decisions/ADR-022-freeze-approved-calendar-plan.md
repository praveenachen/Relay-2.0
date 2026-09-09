# ADR-022-freeze-approved-calendar-plan

Status: Accepted for Phase 6

# Context

ADR-009 already established that an approved action's payload must be an immutable snapshot, not something regenerated at execution time. PLAN adds a wrinkle Notion publishing doesn't have: a schedule can legitimately be regenerated (locked sessions plus remaining availability, re-solved) *before* approval, and a batch of several calendar events can partially fail at execution, which the original immutable-snapshot design didn't need to say anything about.

# Decision

`StudyPlanWorkflowService.request_approval` builds the exact set of `CreateCalendarStudyBlockAction`s from the current sessions and freezes them as a `ProposedAction`; approving snapshots that same payload onto `ApprovalRequest.approved_payload` (ADR-009's existing exact-match check applies unchanged). Setup and session adjustment (`setup`, `adjust_sessions`, and therefore lock/remove/move) are refused once the run is no longer `PLAN_READY` -- specifically, once `AWAITING_APPROVAL` -- so there is no window where the reviewed sessions can drift from what a pending approval already froze. `solve()` (regeneration) is refused for the same reason once approval has been requested. Execution reads only `approval.approved_payload`; there is no second CP-SAT solve or model call after approval, and a partial execution failure (some calendar blocks created, some not) is reported truthfully via `WorkflowStatus.PARTIALLY_COMPLETED` rather than retried or silently upgraded to `COMPLETED`.

# Rationale

Human approval only means something if the thing approved cannot change afterward. Allowing "regenerate" or "edit a session" to remain available during `AWAITING_APPROVAL` would let a student's later edit silently invalidate what they, or a collaborator, already approved, without either party noticing. Confining edits to `PLAN_READY` makes that structurally impossible rather than relying on a runtime check to catch it after the fact.

# Consequences

A student who wants to change something after requesting approval must reject first (`AWAITING_APPROVAL -> REJECTED`, terminal) and start a new run's worth of planning -- there is currently no "amend a pending approval" flow. Partial execution failure keeps every `ExternalArtifact` already created; Relay does not delete successfully created calendar events to simulate an all-or-nothing transaction, matching the project's explicit instruction not to fake atomicity across an external side effect.

# When We Would Reconsider

If real usage shows rejecting-and-restarting after a pending approval is too costly (e.g., losing already-completed Notion import and availability lookups), add an explicit "return to review" transition that revokes the pending `ApprovalRequest` first, rather than loosening the edit-lock itself.
