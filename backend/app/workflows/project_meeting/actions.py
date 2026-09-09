import re
from datetime import date
from typing import Literal

from app.connectors.github.schemas import CreateGitHubIssueAction, RequestPullRequestReviewAction
from app.connectors.notion.action_items import (
    NotionActionItemPropertyMapping,
    build_task_properties,
)
from app.connectors.notion.schemas import CreateNotionTaskAction, NotionBlock
from app.models.entities import ProjectMember, ProjectWorkspace
from app.workflows.lecture_notes.schemas import StrictModel
from app.workflows.project_meeting.deadlines import resolve_relative_date
from app.workflows.project_meeting.identity import MemberCandidate, resolve_identity
from app.workflows.project_meeting.models import MeetingAnalysis, MeetingSourceReference

Destination = Literal["notion", "github"]

_PR_NUMBER = re.compile(r"#(\d+)")

NOTION_TASK_OPERATION = "create_notion_task"
CREATE_GITHUB_ISSUE_OPERATION = "create_github_issue"
REQUEST_GITHUB_PR_REVIEW_OPERATION = "request_github_pr_review"


class PlannedAction(StrictModel):
    """The editable draft a student reviews before approval. Not yet a
    typed provider action -- destinations, owner, and PR number can all
    still be corrected here. See build_notion_task_action /
    build_github_issue_action / build_pull_request_review_action for the
    deterministic conversion into a frozen, approvable payload."""

    id: str
    title: str
    description: str
    category: str
    confidence: str
    source_refs: tuple[MeetingSourceReference, ...] = ()
    owner_name: str | None = None
    member_id: str | None = None
    identity_status: str = "unspecified"
    identity_candidates: tuple[MemberCandidate, ...] = ()
    deadline_text: str | None = None
    deadline_date: str | None = None
    destinations: tuple[Destination, ...] = ()
    labels: tuple[str, ...] = ()
    pull_request_reference: str | None = None
    pull_request_number: int | None = None


def extract_pull_request_number(reference: str | None) -> int | None:
    if not reference:
        return None
    match = _PR_NUMBER.search(reference)
    return int(match.group(1)) if match else None


def default_destinations(
    category: str, *, has_repository: bool, pull_number: int | None
) -> tuple[Destination, ...]:
    """general -> Notion; technical -> Notion (+ GitHub if a repo is
    configured); decision is not planned at all (view-only, never becomes a
    GitHub issue); review request -> GitHub only once a PR is identified."""
    if category == "REVIEW_REQUEST":
        return ("github",) if (has_repository and pull_number) else ()
    if category == "TECHNICAL_TASK":
        return ("notion", "github") if has_repository else ("notion",)
    return ("notion",)


class ActionPlanner:
    def plan(
        self,
        analysis: MeetingAnalysis,
        members: list[ProjectMember],
        project: ProjectWorkspace,
        *,
        meeting_date: date,
    ) -> list[PlannedAction]:
        has_repository = bool(project.github_repository_owner and project.github_repository_name)
        planned: list[PlannedAction] = []
        for index, item in enumerate(analysis.action_items):
            identity = resolve_identity(item.owner_name, members)
            pull_number = extract_pull_request_number(item.pull_request_reference)
            deadline_date = resolve_relative_date(item.deadline_text, meeting_date)
            planned.append(
                PlannedAction(
                    id=f"action-{index + 1}",
                    title=item.title,
                    description=item.description,
                    category=item.category,
                    confidence=item.confidence,
                    source_refs=tuple(item.source_refs),
                    owner_name=item.owner_name,
                    member_id=identity.member_id,
                    identity_status=identity.status,
                    identity_candidates=identity.candidates,
                    deadline_text=item.deadline_text,
                    deadline_date=deadline_date.isoformat() if deadline_date else None,
                    destinations=default_destinations(
                        item.category, has_repository=has_repository, pull_number=pull_number
                    ),
                    pull_request_reference=item.pull_request_reference,
                    pull_request_number=pull_number,
                )
            )
        return planned


def build_notion_task_action(
    draft: PlannedAction,
    *,
    database_id: str,
    mapping: NotionActionItemPropertyMapping,
    connection_id: str | None,
    owner_display_name: str | None,
) -> CreateNotionTaskAction:
    deadline_date_value = date.fromisoformat(draft.deadline_date) if draft.deadline_date else None
    properties = build_task_properties(
        mapping,
        title=draft.title,
        description=draft.description,
        owner_name=owner_display_name or draft.owner_name,
        deadline_date=deadline_date_value,
    )
    body = [NotionBlock(kind="paragraph", text=draft.description)] if draft.description else []
    return CreateNotionTaskAction(
        task_id=draft.id,
        database_id=database_id,
        title=draft.title,
        properties=properties,
        body_blocks=tuple(body),
        connection_id=connection_id,
    )


def build_github_issue_action(
    draft: PlannedAction,
    *,
    repository_owner: str,
    repository_name: str,
    assignee_username: str | None,
    connection_id: str | None,
) -> CreateGitHubIssueAction:
    body = draft.description
    if draft.deadline_text:
        body = f"{body}\n\nDeadline (from meeting): {draft.deadline_text}"
    return CreateGitHubIssueAction(
        task_id=draft.id,
        repository_owner=repository_owner,
        repository_name=repository_name,
        title=draft.title,
        body=body,
        assignees=(assignee_username,) if assignee_username else (),
        labels=draft.labels,
        connection_id=connection_id,
    )


def build_pull_request_review_action(
    draft: PlannedAction,
    *,
    repository_owner: str,
    repository_name: str,
    reviewer_username: str,
    connection_id: str | None,
) -> RequestPullRequestReviewAction | None:
    if not draft.pull_request_number:
        return None
    return RequestPullRequestReviewAction(
        task_id=draft.id,
        repository_owner=repository_owner,
        repository_name=repository_name,
        pull_number=draft.pull_request_number,
        reviewer=reviewer_username,
        connection_id=connection_id,
    )
