# PLAN workflow

PLAN turns Notion academic tasks and Google Calendar availability into a realistic, deterministic study schedule, then creates only the approved study blocks on the student's calendar.

Implemented:

- configurable Notion task database ingestion (property mapping, not a fixed schema)
- Google Calendar OAuth with least-privilege scopes, token refresh, and calendar selection
- real busy-interval retrieval and normalization into Relay's own scheduling types
- a CP-SAT solver that owns every scheduling decision -- no language model ever chooses a time
- task decomposition into multiple sessions bounded by session-length preferences
- hard constraints (no overlap, no work past a deadline, study-hour and break enforcement, locked sessions)
- soft constraints (deadline urgency, priority, preferred time of day, fragmentation, daily balance) as centralized, documented heuristics
- explicit infeasibility reporting (scheduled/unscheduled minutes, conflicts, affected task)
- session review: lock, remove, and regenerate the remaining unlocked work
- human approval of the exact proposed calendar blocks, frozen before execution
- per-event idempotent calendar event creation with truthful partial-failure reporting
- external artifact persistence for every calendar event actually created

The core principle, unchanged from the design brief: **AI may interpret information (parsing a Notion property, summarizing a task title), but the actual calendar time slots are decided by CP-SAT, deterministically, from typed domain data.**

## Linear setup, then review

Session setup (`PUT /setup`, `POST /tasks/import`, `POST /availability`, the first `POST /solve`) only runs while the workflow run is `DRAFT`. Once the first schedule exists the run moves to `PLAN_READY` and setup is locked -- a student reviews, locks/removes/regenerates sessions, and requests approval from there. This is deliberate: letting setup mutate a plan that already has a pending approval would let the approved payload silently drift from what was reviewed. See `docs/architecture/scheduling-engine.md` for the solver and `docs/architecture/plan-sequence.md` for the full request sequence.

## Notion task ingestion

Relay does not assume a fixed Notion schema. `NotionTaskPropertyMapping` names which property holds the title, course, deadline, priority, status, and estimate (with an explicit `estimate_unit` of minutes or hours), plus which status values count as "done". `NotionTaskMapper` turns raw Notion pages into `AcademicTask`s and reports, rather than guesses, when a page is missing a deadline or estimate. A student can select a database and mapping once (`NotionTaskSourceService`, persisted via `NotionTaskDatabaseRecord`) and PLAN reuses it on future runs, or override the mapping per run, or skip Notion entirely and enter tasks directly.

## Calendar availability

`GoogleCalendarService` refreshes and lists the student's calendars and persists which one is the default (`GoogleCalendarRecord`). `GoogleCalendarApiClient.busy_intervals` reads existing events and `busy_interval_from_event` normalizes them into `BusyInterval` -- the CP-SAT solver never sees a raw Google API response, only Relay's own `AcademicTask` / `AvailabilityWindow` / `BusyInterval` / `StudySession` types.

## Approval and execution

`request_approval` freezes the exact proposed `CreateCalendarStudyBlockAction`s as a `ProposedAction`; approving snapshots that same payload as `ApprovalRequest.approved_payload`. Execution reads only the frozen payload -- there is no second solver or model call after approval. Each calendar block is created independently and idempotently; if some succeed and some fail, the run moves to `PARTIALLY_COMPLETED` with the created/failed counts and reasons recorded, and the artifacts already created are kept (see `docs/architecture/plan-sequence.md`).

## Known limitations

- Regeneration only replaces *unlocked* sessions; there is no endpoint to resize a session by dragging in the UI (the review UI supports lock/remove/regenerate, not drag-resize).
- Google Calendar's own idempotency at the write layer is limited to embedding the idempotency key in the event description and `extendedProperties`; Relay's own `LocalExecution`/`ExternalArtifact` records are what actually prevent duplicate creation on retry.
- The direct database connector used by `LocalRuntimeClient` at execution time does not itself refresh an expired Google token; refresh happens on the read paths (`GoogleCalendarService.connection`). If a token expires between approval and execution, the calendar block creation fails with `GOOGLE_AUTHORIZATION_FAILED` and the student must reconnect and re-approve.
- COLLABORATE and `AgentRuntimeHttpClient` are out of scope for this phase.
