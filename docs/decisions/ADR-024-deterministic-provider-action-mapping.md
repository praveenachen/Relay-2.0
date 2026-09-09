# ADR-024-deterministic-provider-action-mapping

Status: Accepted for Phase 7

# Context

`MeetingAnalysis` gives COLLABORATE decisions and action items in plain text: an owner name, a raw deadline phrase, a category, maybe a pull-request reference. None of that is a Notion property payload or a GitHub issue body. Something has to turn extracted text into the typed, provider-shaped actions (`CreateNotionTaskAction`, `CreateGitHubIssueAction`, `RequestPullRequestReviewAction`) that `RuntimeClient` executes -- and per the project's core rule, that something must not be the language model.

# Decision

`ActionPlanner.plan()` and the `build_notion_task_action` / `build_github_issue_action` / `build_pull_request_review_action` functions (`app/workflows/project_meeting/actions.py`) are the entire mapping layer, and they are ordinary synchronous Python with no model call anywhere in them. `ActionPlanner.plan()` takes a `MeetingAnalysis`, the project's `ProjectMember` list, and the `ProjectWorkspace`, and produces one `PlannedAction` draft per action item using a fixed category-to-destination table (`GENERAL_TASK`/`DOCUMENTATION`/`RESEARCH` -> Notion; `TECHNICAL_TASK` -> Notion and, if a repository is configured, GitHub; `REVIEW_REQUEST` -> GitHub only, gated on a pull request number actually being extractable). Decisions are never planned as actions -- they stay read-only context in the review UI. Every draft is fully editable (`PUT /workflows/collaborate/{id}/action-items`) before any `ProposedAction` is created; the `build_*_action` functions run only once, at approval-request time, against the (possibly edited) draft.

# Rationale

Splitting "what should happen" (the LLM's job -- identify tasks and decisions) from "what payload does the provider need" (this layer's job) is the same shape as PLAN's CP-SAT scheduler sitting between LLM-free task input and typed `CreateCalendarEventAction`s: a deterministic, independently testable stage between interpretation and execution. It also resolves what "Approve Selected" means for a workflow with several actions per run: since `WorkflowService`'s state machine only reaches `APPROVED` once every `ProposedAction` on the run is individually approved, selecting a subset has to happen *before* actions are created -- i.e. by removing an unwanted draft during review -- not by half-approving an already-requested batch.

# Consequences

Category-to-destination defaults are a fixed table, not user-configurable in this phase; a team whose workflow doesn't match (e.g. wanting `RESEARCH` items in GitHub too) edits the destination per action item in review rather than changing a setting. Because the mapping functions are pure and take already-resolved data (a member's `github_username`, an already-extracted pull-request number, an already-resolved deadline), `test_action_planning.py` exercises the entire mapping surface without a language model, a database, or a mocked connector.

# When We Would Reconsider

If projects want their own category/destination rules, add a per-`ProjectWorkspace` override table read by `ActionPlanner` -- the planner's pure-function shape already supports that without touching the extraction or execution layers.
