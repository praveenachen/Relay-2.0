from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.connectors.github.client import GitHubApiClient
from app.connectors.github.errors import GitHubUnavailable
from app.connectors.github.mock import MockGitHubConnector
from app.connectors.github.schemas import GitHubCollaborator, GitHubLabel
from app.core.config import get_settings
from app.domain.enums import Provider
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import ConnectedAccount, ExternalArtifact, LocalExecution

TRANSCRIPT = (
    "Sarah: We decided to use Postgres for the database.\n\n"
    "Alex: I'll implement the login API by Thursday.\n\n"
    "Sarah: I'll review Alex's PR #12.\n"
)


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "language_model_provider", "fake")


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        get_settings(),
        "token_encryption_key",
        type("Secret", (), {"get_secret_value": lambda self: key})(),
    )
    return key


async def connect_github(session_factory, account, encryption_key):
    store = FernetCredentialStore([encryption_key])
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=UUID(account["id"]),
                provider=Provider.GITHUB,
                external_account_id="gh-1",
                display_name="Student",
                access_token_encrypted=store.encrypt("gh-token"),
                scopes=["repo"],
                provider_metadata={},
                status="CONNECTED",
            )
        )
        await session.commit()


async def connect_notion(session_factory, account, encryption_key):
    # Collaborate lifecycle tests validate proposal/approval/retry behavior with
    # deterministic connector results. Product/dev defaults can still use real
    # Notion publishing.
    get_settings().notion_publish_mode = "mock"
    store = FernetCredentialStore([encryption_key])
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=UUID(account["id"]),
                provider=Provider.NOTION,
                external_account_id="notion-1",
                display_name="Student Workspace",
                access_token_encrypted=store.encrypt("notion-token"),
                scopes=["insert_content"],
                provider_metadata={"workspace_id": "workspace-1"},
                status="CONNECTED",
            )
        )
        await session.commit()


async def create_project(client, **overrides):
    payload = {
        "name": "Capstone",
        "course": "CS499",
        "notion_database_id": "db-1",
        "notion_property_mapping": {
            "title": "Name",
            "owner": "Owner",
            "deadline": "Due",
            "status": "Status",
            "status_property_type": "select",
            "default_status": "To Do",
        },
        "github_repository_owner": "team",
        "github_repository_name": "app",
    }
    payload.update(overrides)
    response = await client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def add_member(client, project_id, display_name, github_username=None):
    response = await client.post(
        f"/projects/{project_id}/members",
        json={"display_name": display_name, "github_username": github_username},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def start_run(client, project_id):
    created = await client.post("/workflows/collaborate", json={"project_id": project_id})
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def analyzed_run(client, session_factory, account, encryption_key, *, transcript=TRANSCRIPT):
    await connect_github(session_factory, account, encryption_key)
    await connect_notion(session_factory, account, encryption_key)
    project = await create_project(client)
    await add_member(client, project["id"], "Alex Kim", github_username="alexk")
    await add_member(client, project["id"], "Sarah Chen", github_username="sarahc")
    run_id = await start_run(client, project["id"])
    path = f"/workflows/collaborate/{run_id}"
    uploaded = await client.post(
        path + "/transcript",
        files={"file": ("meeting.txt", transcript.encode(), "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    parsed = await client.post(path + "/parse", params={"meeting_date": "2026-01-05"})
    assert parsed.status_code == 200, parsed.text
    analyzed = await client.post(path + "/analyze")
    assert analyzed.status_code == 200, analyzed.text
    return path, analyzed.json(), project


def _mock_repository_facts(monkeypatch):
    async def list_collaborators(self, owner, name):
        return [GitHubCollaborator(login="alexk"), GitHubCollaborator(login="sarahc")]

    async def list_labels(self, owner, name):
        return [GitHubLabel(name="bug")]

    monkeypatch.setattr(GitHubApiClient, "list_collaborators", list_collaborators)
    monkeypatch.setattr(GitHubApiClient, "list_labels", list_labels)


async def approve_all(client, detail):
    for approval in detail["approvals"]:
        response = await client.post(
            f"/approvals/{approval['id']}/approve",
            json={"approved_payload": approval["original_payload"]},
        )
        assert response.status_code == 200, response.text


async def test_analysis_produces_decisions_and_planned_action_items(
    client, account, session_factory, encryption_key
):
    _path, detail, _project = await analyzed_run(client, session_factory, account, encryption_key)
    assert detail["run"]["status"] == "PLAN_READY"
    assert len(detail["decisions"]) == 1
    action_items = detail["action_items"]
    assert len(action_items) == 2
    technical = next(item for item in action_items if item["category"] == "TECHNICAL_TASK")
    assert technical["identity_status"] == "resolved"
    assert technical["deadline_date"] == "2026-01-08"
    assert set(technical["destinations"]) == {"notion", "github"}
    review = next(item for item in action_items if item["category"] == "REVIEW_REQUEST")
    assert review["pull_request_number"] == 12
    assert review["destinations"] == ["github"]


async def test_editing_action_items_persists_owner_correction(
    client, account, session_factory, encryption_key
):
    path, detail, _project = await analyzed_run(client, session_factory, account, encryption_key)
    items = detail["action_items"]
    items[0]["destinations"] = []
    response = await client.put(path + "/action-items", json={"action_items": items})
    assert response.status_code == 200, response.text
    assert response.json()["action_items"][0]["destinations"] == []


async def test_full_lifecycle_approve_and_execute_across_notion_and_github(
    client, account, session_factory, encryption_key, monkeypatch
):
    _mock_repository_facts(monkeypatch)
    path, detail, _project = await analyzed_run(client, session_factory, account, encryption_key)

    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    detail = requested.json()
    assert len(detail["approvals"]) == 3
    assert (await client.get(f"/workflow-runs/{_run_id(path)}")).json()[
        "status"
    ] == "AWAITING_APPROVAL"

    await approve_all(client, detail)
    run_after_approval = await client.get(f"/workflow-runs/{_run_id(path)}")
    assert run_after_approval.json()["status"] == "APPROVED"

    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"
    payload = done.json()["result_payload"]
    assert payload["succeeded_count"] == 3
    assert payload["failed_count"] == 0

    async with session_factory() as session:
        artifact_types = (await session.scalars(select(ExternalArtifact.artifact_type))).all()
        assert sorted(artifact_types) == ["github_issue", "github_review_request", "notion_task"]

    again = await client.post(path + "/execute")
    assert again.json()["result_payload"] == done.json()["result_payload"]
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(ExternalArtifact))) == 3
        assert (await session.scalar(select(func.count()).select_from(LocalExecution))) == 3


async def test_partial_failure_preserves_successful_artifacts(
    client, account, session_factory, encryption_key, monkeypatch
):
    _mock_repository_facts(monkeypatch)
    path, detail, _project = await analyzed_run(client, session_factory, account, encryption_key)

    async def failing_create_issue(self, action, idempotency_key):
        raise GitHubUnavailable()

    monkeypatch.setattr(MockGitHubConnector, "create_issue", failing_create_issue)

    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    detail = requested.json()
    await approve_all(client, detail)

    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "PARTIALLY_COMPLETED"
    payload = done.json()["result_payload"]
    assert payload["succeeded_count"] == 2
    assert payload["failed_count"] == 1

    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(ExternalArtifact))) == 2

    events = (await client.get(f"/workflow-runs/{_run_id(path)}/events")).json()
    assert any(e["event_type"] == "GITHUB_ACTION_FAILED" for e in events)
    assert not any(e["event_type"] == "WORKFLOW_COMPLETED" for e in events)

    assert (await client.post(path + "/execute")).status_code == 409


async def test_review_request_without_identifiable_pr_is_unresolved(
    client, account, session_factory, encryption_key, monkeypatch
):
    _mock_repository_facts(monkeypatch)
    transcript = (
        "Sarah: We decided to use Postgres for the database.\n\n"
        "Alex: I'll implement the login API by Thursday.\n\n"
        "Sarah: I'll review Alex's pull request.\n"
    )
    path, detail, _project = await analyzed_run(
        client, session_factory, account, encryption_key, transcript=transcript
    )
    review = next(item for item in detail["action_items"] if item["category"] == "REVIEW_REQUEST")
    assert review["pull_request_number"] is None
    assert review["destinations"] == []

    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    # Only the technical task's Notion + GitHub actions are proposed; the
    # unresolved review request is skipped, not silently guessed.
    assert len(requested.json()["approvals"]) == 2


async def test_no_bypass_without_approval(client, account, session_factory, encryption_key):
    path, _detail, _project = await analyzed_run(client, session_factory, account, encryption_key)
    assert (await client.post(path + "/execute")).status_code == 409


def _run_id(path: str) -> str:
    return path.rsplit("/", 1)[-1]
