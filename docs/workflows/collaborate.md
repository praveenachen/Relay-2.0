# COLLABORATE workflow

COLLABORATE turns a group-project meeting transcript into typed Notion tasks and GitHub work, reviewed and approved before anything is created.

Implemented:

- a lightweight persistent `ProjectWorkspace` / `ProjectMember` model so a transcript never has to identify its own repository or teammates
- transcript normalization (pasted text, TXT, Markdown, DOCX) into Relay-owned `MeetingTranscript` / `MeetingSegment` types, preserving speaker, order, and timestamp where available
- typed LLM extraction (`MeetingAnalysis`: decisions, action items, unresolved questions) that never invents an owner, a deadline, or a pull request reference
- deterministic member identity resolution (exact match, ambiguous, unresolved -- never a guess)
- a deterministic action planner that maps action items to typed `CreateNotionTaskAction` / `CreateGitHubIssueAction` / `RequestPullRequestReviewAction` payloads
- real GitHub integration (OAuth, repository/collaborator/label/pull-request reads, issue creation, review requests)
- real Notion database-page writing (extending the existing Notion connector, not a second client)
- human approval of the exact typed payloads, one `ProposedAction` per action item per destination
- independent multi-system execution with truthful partial completion
- idempotent execution and `ExternalArtifact` persistence per action

The core rule, unchanged from the design brief: **LLM interpretation stops before external-system execution.** The model identifies tasks, owners, deadlines, decisions, and technical work in plain text; it never produces a Notion property payload or a GitHub API call. `ActionPlanner` and the two `build_*_action` functions in `app/workflows/project_meeting/actions.py` are the only code that turns an extracted action item into something a provider actually receives, and they are ordinary, tested Python functions -- not a model call.

## Project context

`ProjectWorkspace` (name, course, `notion_database_id`, `notion_property_mapping`, `github_repository_owner`/`github_repository_name`) and `ProjectMember` (display name, email, `notion_identity`, `github_username`) are created once per team/course and reused across every meeting. This is deliberately not a project-management product -- there is no task board, no due-date tracking independent of a meeting, no cross-project reporting. It exists only so a transcript's "Sarah" or "the repo" can resolve to something real instead of being inferred by a model.

## Transcript normalization

`app/workflows/project_meeting/transcript.py::parse_transcript` recognizes `Speaker: text` and `[timestamp] Speaker:` (text on following lines) turns; anything else becomes a speaker-less segment rather than being dropped. This is a heuristic, not a formal grammar -- see the code comment on `_SPEAKER_LINE` for the one known false-positive shape (a sentence that happens to start with a short capitalized word and a colon). An empty transcript is rejected before it ever reaches the model (`EmptyTranscript`).

Upload reuses LEARN's existing `DocumentService` / `LocalFileStore` / `SourceDocument` infrastructure exactly (see `docs/architecture/document-processing.md`) rather than building a second upload path; a DOCX transcript's parsed sections are flattened back into raw text before `parse_transcript` runs, since `ParsedDocument.sections` is structured around lecture headings, not speaker turns.

## Typed extraction and provenance

`MeetingAnalysisService` (`app/workflows/project_meeting/analysis.py`) sends the transcript's segments (with their ids) to the configured `LanguageModel` and validates the result the same way LEARN validates source references: every decision and action item's `source_refs` must point at a real segment id, or the whole analysis is rejected as malformed (`MalformedModelOutput`, reused from LEARN's error module -- see the note in `docs/decisions/ADR-023-typed-meeting-extraction.md` about that reuse). The prompt (`app/workflows/project_meeting/prompts.py`) explicitly forbids inventing an owner or a deadline and requires leaving them null when the transcript doesn't state them, and explicitly tells the model the transcript is untrusted data, never instructions.

Deadlines are a deliberate two-step split: the model extracts only the raw phrase it saw ("Thursday", "next week", "in two days") into `deadline_text`; a separate, deterministic function (`app/workflows/project_meeting/deadlines.py::resolve_relative_date`) turns common phrases into an actual date relative to the meeting date. Phrases it doesn't recognize resolve to `None` rather than a guess, and stay editable in the review UI.

## Identity resolution

`app/workflows/project_meeting/identity.py::resolve_identity` matches a transcript's `owner_name` against `ProjectMember.display_name`, exact match first, then first-token match, and reports one of `resolved` / `ambiguous` / `unresolved` / `unspecified` -- never a guess. An ambiguous match carries every candidate member so the review UI can ask the student to pick, rather than picking for them. A resolved member's GitHub username is used for issue assignment only if the member actually has one recorded; a missing mapping means the issue is still created, just without an assignee (see `docs/decisions/ADR-025-member-identity-resolution.md`).

## Action planning

`ActionPlanner.plan()` (`app/workflows/project_meeting/actions.py`) is pure and synchronous: given a `MeetingAnalysis`, the project's members, and the project itself, it produces one `PlannedAction` draft per action item with a default set of destinations:

- `GENERAL_TASK`, `DOCUMENTATION`, `RESEARCH` -> Notion only
- `TECHNICAL_TASK` -> Notion, plus GitHub if the project has a configured repository
- `REVIEW_REQUEST` -> GitHub only, and only once a pull request number can be extracted from the transcript's own text (`extract_pull_request_number`); otherwise the draft has no destinations and stays visibly unresolved
- decisions are never planned as actions at all -- they are read-only context in the review UI, not something that becomes a GitHub issue

These defaults are fully editable in review (`PUT /workflows/collaborate/{id}/action-items`) before anything is proposed for approval.

## Approval shape

Unlike LEARN (one action) or PLAN (one action containing many sub-events), a COLLABORATE run typically proposes several independent `ProposedAction`s -- one per action item per destination. `WorkflowService.request_approvals` already supported this (it loops over every action on a run); each gets its own `ApprovalRequest`, approved or rejected individually through the existing `/approvals/{id}/approve|reject` endpoints. "Approve Selected" is expressed by removing unwanted drafts during review before requesting approval, not by leaving some of an already-requested batch approved and others pending forever -- see `docs/decisions/ADR-024-deterministic-provider-action-mapping.md` for why, and `docs/architecture/workflow-state-machine.md` for the underlying gate (a run only reaches `APPROVED` once every one of its actions is individually approved).

## Execution and partial completion

`CollaborateExecutionService` (`app/workflows/project_meeting/execution.py`) submits each approved action to `RuntimeClient` independently -- one Notion task, one GitHub issue, one review request are three separate `submit_execution` calls, each with its own idempotency key (`collaborate:{run_id}:{action_id}`). The run's aggregate result is derived from the individual outcomes: all succeeded -> `COMPLETED`; some succeeded -> `PARTIALLY_COMPLETED` with the exact succeeded/failed counts in `result_payload`; none succeeded -> `FAILED`. Artifacts already created are never rolled back because a sibling action failed. See `docs/architecture/collaborate-sequence.md`.

## Known limitations

- GitHub label/assignee validation before approval is best-effort: if the GitHub connection or a live API call fails at that moment, invalid entries are silently dropped rather than the whole approval round being blocked, and the real validation still happens at execution time via typed errors.
- `AssignGitHubIssueAction` (assigning an *existing* issue Relay didn't create) is not implemented -- assignment only happens at issue-creation time via `CreateGitHubIssueAction.assignees`, since the transcript-analysis flow does not identify pre-existing issue numbers to assign against.
- No Playwright end-to-end test was added for COLLABORATE (the backend integration suite in `tests/test_collaborate.py` covers the full lifecycle at the same depth LEARN's and PLAN's do); a browser-level test would need Notion and GitHub mocked inside `backend/tests/browser_server.py`.
- The shared `MalformedModelOutput` / `ModelUnavailable` / `ModelTimeout` / `ModelRateLimited` errors are LEARN-named (raised inside the shared `OpenAIProvider`) but reused here for COLLABORATE's own model failures; the `code`/status mapping is correct, the message text still says "study notes" in some cases.
