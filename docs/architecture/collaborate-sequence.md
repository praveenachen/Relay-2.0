# COLLABORATE sequence

## Transcript through plan-ready analysis

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant Docs as DocumentService
    participant Model as LanguageModel
    participant Planner as ActionPlanner
    participant DB as Database

    Student->>UI: Choose or create a project
    UI->>API: POST /workflows/collaborate {project_id}
    API->>DB: Create run (DRAFT, project_workspace_id set)
    Student->>UI: Provide transcript (paste or file)
    UI->>API: POST /{id}/transcript
    API->>Docs: validate + store (reuses LEARN's SourceDocument path)
    API->>DB: Save source
    Student->>UI: Extract segments
    UI->>API: POST /{id}/parse
    API->>API: parse_transcript() -- deterministic, no model call
    API->>DB: Save MeetingTranscript, transition DRAFT -> ANALYZING
    Student->>UI: Analyze meeting
    UI->>API: POST /{id}/analyze
    API->>Model: generate_structured(segments, MeetingAnalysis)
    Model-->>API: decisions, action items (owner/deadline/PR refs as raw text only)
    API->>API: validate_references() against real segment ids
    API->>Planner: plan(analysis, project members, project)
    Planner-->>API: PlannedAction[] (identity resolved, deadlines resolved, destinations defaulted)
    API->>DB: Save plan, transition ANALYZING -> PLAN_READY
    API-->>UI: Decisions, action items, unresolved questions
```

Extraction is the only step that calls a language model. Everything after it -- identity resolution, deadline resolution, destination defaults, and the eventual typed payloads -- is ordinary deterministic code, exercised directly by unit tests with no model involved.

## Review, approval, and the multi-action shape

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant GitHub as GitHubService
    participant DB as Database

    Student->>UI: Correct an owner, deadline, or destination
    UI->>API: PUT /{id}/action-items
    API->>DB: Save edited drafts (still PLAN_READY)
    Student->>UI: Request approval
    UI->>API: POST /{id}/approval
    API->>GitHub: collaborators() + labels() (best-effort validation)
    GitHub-->>API: valid logins and label names
    loop each remaining action item x each of its destinations
        API->>API: build_notion_task_action / build_github_issue_action / build_pull_request_review_action
        API->>DB: Create one ProposedAction (Notion or GitHub)
    end
    API->>DB: request_approvals() -- one ApprovalRequest per action, transition -> AWAITING_APPROVAL
    loop each ApprovalRequest
        Student->>UI: Approve or reject this action
        UI->>API: POST /approvals/{approval_id}/approve|reject
    end
    API->>DB: transition -> APPROVED once every action is individually approved
```

A run's `AWAITING_APPROVAL` -> `APPROVED` transition already required every action's approval to be `APPROVED` before this phase (see `docs/architecture/workflow-state-machine.md`); COLLABORATE is simply the first workflow where "every action" is routinely more than one. "Approve Selected" happens by removing an unwanted draft during review, before any `ProposedAction` exists for it -- not by leaving one action's approval pending forever while others proceed.

## Independent execution and partial completion

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant Runtime as LocalRuntimeClient
    participant Notion as NotionApiClient
    participant GitHub as GitHubApiClient
    participant DB as Database

    Student->>UI: Create approved Notion and GitHub work
    UI->>API: POST /{id}/execute
    API->>DB: transition APPROVED -> QUEUED -> EXECUTING
    loop each approved action, independently
        API->>Runtime: submit_execution(operation, approved_payload, "collaborate:{run}:{action}")
        alt create_notion_task
            Runtime->>Notion: POST /v1/pages (parent: database)
        else create_github_issue
            Runtime->>GitHub: POST /repos/{owner}/{name}/issues
        else request_github_pr_review
            Runtime->>GitHub: POST .../pulls/{n}/requested_reviewers
        end
        alt succeeds
            Runtime-->>API: result with external_id/external_url
            API->>DB: Record ExternalArtifact (notion_task / github_issue / github_review_request)
        else fails
            Runtime-->>API: raises; caught per action
        end
    end
    API->>DB: succeeded == total -> COMPLETED
    API->>DB: 0 < succeeded < total -> PARTIALLY_COMPLETED (artifacts kept)
    API->>DB: succeeded == 0 -> FAILED
    API-->>UI: result_payload {succeeded_count, failed_count, total_count}
```

Unlike PLAN (one `ProposedAction` containing many calendar-block sub-events, aggregated inside `LocalRuntimeClient`), COLLABORATE's actions are already independent `ProposedAction` rows, so the aggregation happens one level up, in `CollaborateExecutionService`, over N separate `RuntimeClient.submit_execution` calls. Both arrive at the same truthful outcome: successfully created artifacts are never discarded because a sibling action failed, and the run's terminal state says exactly how much of what was approved actually happened.
