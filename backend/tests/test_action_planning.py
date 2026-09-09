from datetime import date
from uuid import uuid4

from app.workflows.project_meeting.actions import (
    ActionPlanner,
    build_github_issue_action,
    build_notion_task_action,
    build_pull_request_review_action,
    default_destinations,
    extract_pull_request_number,
)
from app.workflows.project_meeting.deadlines import resolve_relative_date
from app.workflows.project_meeting.models import MeetingActionItem, MeetingAnalysis


class FakeMember:
    def __init__(self, display_name: str, github_username: str | None = None):
        self.id = uuid4()
        self.display_name = display_name
        self.github_username = github_username


class FakeProject:
    def __init__(self, github_repository_owner=None, github_repository_name=None):
        self.github_repository_owner = github_repository_owner
        self.github_repository_name = github_repository_name


def action_item(**overrides) -> MeetingActionItem:
    data = {
        "title": "Implement auth",
        "description": "Implement authentication",
        "owner_name": "Sarah",
        "category": "GENERAL_TASK",
        "confidence": "high",
        "source_refs": [],
    }
    data.update(overrides)
    return MeetingActionItem(**data)


def test_general_task_defaults_to_notion_only():
    destinations = default_destinations("GENERAL_TASK", has_repository=True, pull_number=None)
    assert destinations == ("notion",)


def test_technical_task_defaults_to_notion_and_github_when_repo_configured():
    destinations = default_destinations("TECHNICAL_TASK", has_repository=True, pull_number=None)
    assert set(destinations) == {"notion", "github"}


def test_technical_task_is_notion_only_without_a_repository():
    destinations = default_destinations("TECHNICAL_TASK", has_repository=False, pull_number=None)
    assert destinations == ("notion",)


def test_decision_is_never_planned_as_a_destination():
    # Decisions aren't action items at all -- ActionPlanner only plans
    # analysis.action_items, so a decision never reaches default_destinations.
    analysis = MeetingAnalysis(
        summary="",
        decisions=[{"title": "Use Postgres", "description": "Use Postgres", "source_refs": []}],
        action_items=[],
    )
    planned = ActionPlanner().plan(analysis, [], FakeProject(), meeting_date=date(2026, 1, 5))
    assert planned == []


def test_review_request_resolves_only_with_an_identified_pull_request():
    resolved = default_destinations("REVIEW_REQUEST", has_repository=True, pull_number=12)
    assert resolved == ("github",)
    unresolved = default_destinations("REVIEW_REQUEST", has_repository=True, pull_number=None)
    assert unresolved == ()


def test_extract_pull_request_number_from_reference_text():
    assert extract_pull_request_number("PR #12") == 12
    assert extract_pull_request_number("Sarah's PR") is None
    assert extract_pull_request_number(None) is None


def test_planner_resolves_identity_and_deadline_and_pull_request():
    sarah = FakeMember("Sarah Chen", github_username="sarahc")
    analysis = MeetingAnalysis(
        summary="",
        decisions=[],
        action_items=[
            action_item(
                owner_name="Sarah Chen",
                deadline_text="tomorrow",
                category="TECHNICAL_TASK",
            ),
            action_item(
                title="Review PR",
                description="Review Sarah's PR",
                owner_name="Alex",
                category="REVIEW_REQUEST",
                pull_request_reference="PR #7",
            ),
        ],
    )
    project = FakeProject(github_repository_owner="team", github_repository_name="app")
    planned = ActionPlanner().plan(analysis, [sarah], project, meeting_date=date(2026, 1, 5))
    assert planned[0].member_id == str(sarah.id)
    assert planned[0].deadline_date == "2026-01-06"
    assert set(planned[0].destinations) == {"notion", "github"}
    assert planned[1].identity_status == "unresolved"
    assert planned[1].pull_request_number == 7
    assert planned[1].destinations == ("github",)


def test_build_notion_task_action_uses_resolved_owner_display_name():
    from app.connectors.notion.action_items import NotionActionItemPropertyMapping

    draft = ActionPlanner().plan(
        MeetingAnalysis(summary="", decisions=[], action_items=[action_item()]),
        [FakeMember("Sarah Chen")],
        FakeProject(),
        meeting_date=date(2026, 1, 5),
    )[0]
    action = build_notion_task_action(
        draft,
        database_id="db-1",
        mapping=NotionActionItemPropertyMapping(title="Name", owner="Owner"),
        connection_id="conn-1",
        owner_display_name="Sarah Chen",
    )
    assert action.properties["Owner"]["rich_text"][0]["text"]["content"] == "Sarah Chen"


def test_build_github_issue_action_omits_assignee_without_github_username():
    draft = ActionPlanner().plan(
        MeetingAnalysis(summary="", decisions=[], action_items=[action_item()]),
        [FakeMember("Sarah Chen", github_username=None)],
        FakeProject(github_repository_owner="team", github_repository_name="app"),
        meeting_date=date(2026, 1, 5),
    )[0]
    action = build_github_issue_action(
        draft,
        repository_owner="team",
        repository_name="app",
        assignee_username=None,
        connection_id="conn-1",
    )
    assert action.assignees == ()


def test_build_pull_request_review_action_none_without_pull_number():
    draft = ActionPlanner().plan(
        MeetingAnalysis(
            summary="",
            decisions=[],
            action_items=[action_item(category="REVIEW_REQUEST", pull_request_reference=None)],
        ),
        [],
        FakeProject(),
        meeting_date=date(2026, 1, 5),
    )[0]
    assert (
        build_pull_request_review_action(
            draft,
            repository_owner="team",
            repository_name="app",
            reviewer_username="alexk",
            connection_id=None,
        )
        is None
    )


def test_resolve_relative_date_handles_common_phrases():
    monday = date(2026, 1, 5)
    assert resolve_relative_date("tomorrow", monday) == date(2026, 1, 6)
    assert resolve_relative_date("today", monday) == monday
    assert resolve_relative_date("thursday", monday) == date(2026, 1, 8)
    assert resolve_relative_date("next monday", monday) == date(2026, 1, 12)
    assert resolve_relative_date("in 3 days", monday) == date(2026, 1, 8)
    assert resolve_relative_date(None, monday) is None
    assert resolve_relative_date("sometime soon", monday) is None
