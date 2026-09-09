# PLAN sequence

## Setup through first schedule

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant Notion as NotionTaskSourceService
    participant Google as GoogleCalendarService
    participant Solver as CPSATStudyScheduler
    participant DB as Database

    Student->>UI: Choose window, calendar, task source
    UI->>API: PUT /workflows/plan/{id}/setup
    API->>DB: Save setup payload (DRAFT)
    Student->>UI: Import tasks
    UI->>API: POST /tasks/import
    API->>Notion: query_database + NotionTaskMapper
    Notion-->>API: AcademicTask[] + TaskMappingIssue[]
    API->>DB: Save tasks and issues
    Student->>UI: Load availability
    UI->>API: POST /availability
    API->>Google: busy_intervals(calendar_id, window)
    Google-->>API: BusyInterval[]
    API->>DB: Save busy intervals
    Student->>UI: Generate study plan
    UI->>API: POST /solve
    API->>Solver: solve(SchedulingProblem)
    Solver-->>API: SchedulingResult (deterministic)
    API->>DB: Save result, transition DRAFT -> ANALYZING -> PLAN_READY
    API-->>UI: Sessions, metrics, conflicts
```

Every step from setup through the first `solve()` requires the run to still be `DRAFT`; once `PLAN_READY`, setup calls are refused (`PLAN_WORKFLOW_INVALID_STATE`, 409) so a pending review can never be edited out from under itself. `solve()` remains callable again while `PLAN_READY` (regeneration), but not once `AWAITING_APPROVAL`, for the same reason -- see `StudyPlanWorkflowService.solve` and `.adjust_sessions`.

## Review, lock, regenerate, approve

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant Solver as CPSATStudyScheduler
    participant DB as Database

    Student->>UI: Lock a session
    UI->>API: POST /sessions/{id}/lock
    API->>DB: Save sessions (locked flag set)
    Student->>UI: Regenerate remaining
    UI->>API: POST /solve
    API->>Solver: solve(problem with locked_sessions)
    Solver-->>API: Locked session preserved + new sessions for remaining work
    API->>DB: Save result
    Student->>UI: Request approval
    UI->>API: POST /approval
    API->>DB: Freeze CreateCalendarStudyPlanAction as ProposedAction
    API->>DB: Create ApprovalRequest, transition PLAN_READY -> AWAITING_APPROVAL
    Student->>UI: Approve
    UI->>API: POST /approvals/{id}/approve (exact original_payload)
    API->>DB: Store approved_payload, transition -> APPROVED
```

The approved payload is the exact set of `CreateCalendarStudyBlockAction`s built from the sessions at request-approval time. There is no second solver or model call after this point -- execution only ever reads `approval.approved_payload`.

## Execution and partial failure

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant Runtime as LocalRuntimeClient
    participant Connector as DatabaseGoogleCalendarConnector
    participant Google as Google Calendar API
    participant DB as Database

    Student->>UI: Create approved calendar blocks
    UI->>API: POST /execute
    API->>DB: transition APPROVED -> QUEUED -> EXECUTING
    API->>Runtime: submit_execution(approved_payload, idempotency_key)
    Runtime->>DB: Check idempotency_key (LocalExecution)
    loop each approved study block, independently
        Runtime->>Connector: create_study_block(event, key:index)
        Connector->>Google: POST /calendars/{id}/events
        alt succeeds
            Google-->>Connector: event id/url
            Connector-->>Runtime: CalendarEventResult
        else fails (rate limit, timeout, ...)
            Connector-->>Runtime: raises; caught per-event
        end
    end
    Runtime-->>API: ExecutionSnapshot (SUCCEEDED / PARTIAL / FAILED)
    API->>DB: Record ExternalArtifact for every block actually created
    alt all succeeded
        API->>DB: transition -> COMPLETED
    else some succeeded, some failed
        API->>DB: transition -> PARTIALLY_COMPLETED (artifacts kept)
    else none succeeded
        API->>DB: transition -> FAILED
    end
    API-->>UI: created/failed counts, error_code
```

## Partial-failure decision

Each calendar block is created in its own `try`/`except` inside `LocalRuntimeClient.submit_execution` (the `PLAN_OPERATION` branch) -- one failing event does not abort the events already created for other tasks, and the successes are still recorded. `ExecutionStatus` has a `PARTIAL` value alongside `SUCCEEDED`/`FAILED` specifically so `StudyPlanExecutionService.execute` can tell "created some, not all" apart from "created none," and reports it as `WorkflowStatus.PARTIALLY_COMPLETED` -- the same terminal state the state machine already reserved for this since its first migration. `ProposedAction.status` has no partial variant (unlike `WorkflowStatus`, which already anticipated this at the database level); a not-fully-completed action is recorded as `FAILED` at the action level while the *run*-level status and `result_payload` (`created_count`, `failed_count`, `approved_count`) carry the truthful, granular outcome. `PARTIALLY_COMPLETED` is terminal in `TRANSITIONS` -- there is no automatic retry of the failed remainder; a student sees exactly what succeeded (with real calendar links, via the recorded `ExternalArtifact`s) and what didn't.

## Idempotency

Two layers, matching the Notion pattern in `docs/integrations/notion.md`:

1. **Whole-batch**: `LocalExecution.idempotency_key` (`plan:{run_id}:{approval_id}`) short-circuits re-execution of an already-submitted batch, returning the stored snapshot unchanged.
2. **Per-event**: `ExternalArtifact.idempotency_key` (`plan:{run_id}:{approval_id}:{event_index}`) is checked before creating each artifact row, so even if execution logic ran twice for the same event, no duplicate `ExternalArtifact` (and, in practice, no duplicate Google event, since the per-event key is also embedded in the outbound request) would result.
