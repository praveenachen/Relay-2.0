from datetime import UTC, datetime
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.connectors.google.calendar import GoogleCalendarApiClient
from app.connectors.google.errors import CalendarRateLimited
from app.connectors.google.schemas import CalendarEventResult
from app.core.config import get_settings
from app.domain.enums import Provider
from app.models.entities import ConnectedAccount, ExternalArtifact, LocalExecution


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        get_settings(),
        "token_encryption_key",
        type("Secret", (), {"get_secret_value": lambda self: key})(),
    )
    return key


async def no_busy_intervals(self, *args, **kwargs):
    return []


def task_payload(
    task_id: str,
    *,
    deadline: str = "2026-01-08T17:00:00+00:00",
    minutes: int = 120,
    priority: int = 3,
):
    return {
        "id": task_id,
        "title": task_id.replace("-", " ").title(),
        "course": "CSC101",
        "deadline": deadline,
        "estimated_minutes": minutes,
        "priority": priority,
        "status": "todo",
    }


async def connect_google(session_factory, account, encryption_key, *, calendar_id="primary"):
    from app.infrastructure.credentials import FernetCredentialStore

    store = FernetCredentialStore([encryption_key])
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=UUID(account["id"]),
                provider=Provider.GOOGLE,
                external_account_id="google-user-1",
                display_name="student@example.com",
                access_token_encrypted=store.encrypt("google-token"),
                refresh_token_encrypted=store.encrypt("google-refresh"),
                token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                scopes=["https://www.googleapis.com/auth/calendar.events"],
                provider_metadata={
                    "default_calendar_id": calendar_id,
                    "default_calendar_summary": "Primary",
                },
                status="CONNECTED",
            )
        )
        await session.commit()


async def start_and_setup(
    client, *, tasks, start="2026-01-05T00:00:00+00:00", end="2026-01-12T00:00:00+00:00"
):
    created = await client.post("/workflows/plan")
    assert created.status_code == 201, created.text
    path = "/workflows/plan/" + created.json()["id"]
    setup = await client.put(
        path + "/setup",
        json={
            "start": start,
            "end": end,
            "calendar_id": None,
            "notion_database_id": None,
            "notion_mapping": None,
            "tasks": tasks,
        },
    )
    assert setup.status_code == 200, setup.text
    return path, setup.json()


async def ready(client, session_factory, account, encryption_key, *, tasks=None):
    await connect_google(session_factory, account, encryption_key)
    path, detail = await start_and_setup(client, tasks=tasks or [task_payload("essay")])
    imported = await client.post(path + "/tasks/import")
    assert imported.status_code == 200, imported.text
    availability = await client.post(path + "/availability")
    assert availability.status_code == 200, availability.text
    solved = await client.post(path + "/solve")
    assert solved.status_code == 200, solved.text
    return path, solved.json()


async def approve(client, detail):
    approval = detail["approval"]
    response = await client.post(
        f"/approvals/{approval['id']}/approve",
        json={"approved_payload": approval["original_payload"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def fake_create_event(succeed_ids: set[str] | None = None, fail_ids: set[str] | None = None):
    async def create_event(self, action, idempotency_key):
        if fail_ids and action.task_id in fail_ids:
            raise CalendarRateLimited()
        return CalendarEventResult(
            external_id=f"event-{idempotency_key}",
            external_url=f"https://calendar/event-{idempotency_key}",
            title=action.title,
            calendar_id=action.calendar_id,
            start=action.start,
            end=action.end,
        )

    return create_event


async def test_new_plan_detail_has_null_setup(client, account):
    created = await client.post("/workflows/plan")
    assert created.status_code == 201, created.text

    detail = await client.get("/workflows/plan/" + created.json()["id"])

    assert detail.status_code == 200, detail.text
    assert detail.json()["setup"] is None
    assert detail.json()["result"] is None
    assert detail.json()["approval"] is None


async def test_solve_schedules_task_within_window(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    path, detail = await ready(client, session_factory, account, encryption_key)
    assert detail["run"]["status"] == "PLAN_READY"
    result = detail["result"]
    assert result["status"] in {"OPTIMAL", "FEASIBLE"}
    assert result["metrics"]["tasks_fully_scheduled"] == 1
    assert len(result["sessions"]) >= 1


async def test_infeasible_schedule_reports_conflicts(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    await connect_google(session_factory, account, encryption_key)
    path, _ = await start_and_setup(
        client,
        tasks=[task_payload("impossible", deadline="2026-01-05T02:00:00+00:00", minutes=600)],
        start="2026-01-05T00:00:00+00:00",
        end="2026-01-05T03:00:00+00:00",
    )
    await client.post(path + "/tasks/import")
    await client.post(path + "/availability")
    solved = await client.post(path + "/solve")
    assert solved.status_code == 200, solved.text
    result = solved.json()["result"]
    assert result["status"] == "INFEASIBLE"
    assert result["conflicts"][0]["code"] == "UNSCHEDULED_WORK"
    events = (await client.get(f"/workflow-runs/{solved.json()['run']['id']}/events")).json()
    assert any(e["event_type"] == "SCHEDULING_INFEASIBLE" for e in events)
    assert (await client.post(path + "/approval")).status_code == 422


async def test_lock_and_regenerate_preserves_locked_session(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    path, detail = await ready(client, session_factory, account, encryption_key)
    session_id = detail["result"]["sessions"][0]["id"]
    locked = await client.post(
        path + f"/sessions/{session_id}/lock",
        json={"session_id": session_id, "locked": True},
    )
    assert locked.status_code == 200, locked.text
    assert any(s["locked"] for s in locked.json()["setup"]["sessions"])

    regenerated = await client.post(path + "/solve")
    assert regenerated.status_code == 200, regenerated.text
    sessions = regenerated.json()["result"]["sessions"]
    assert any(s["id"] == session_id and s["locked"] for s in sessions)

    unlocked = await client.post(
        path + f"/sessions/{session_id}/lock",
        json={"session_id": session_id, "locked": False},
    )
    assert unlocked.status_code == 200, unlocked.text
    assert all(not s["locked"] for s in unlocked.json()["setup"]["sessions"])


async def test_remove_session(client, account, session_factory, encryption_key, monkeypatch):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    path, detail = await ready(client, session_factory, account, encryption_key)
    session_id = detail["result"]["sessions"][0]["id"]
    removed = await client.delete(path + f"/sessions/{session_id}")
    assert removed.status_code == 200, removed.text
    assert all(s["id"] != session_id for s in removed.json()["setup"]["sessions"])


async def test_full_lifecycle_approve_and_execute(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    monkeypatch.setattr(GoogleCalendarApiClient, "create_event", fake_create_event())
    path, detail = await ready(client, session_factory, account, encryption_key)
    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    assert requested.json()["run"]["status"] == "AWAITING_APPROVAL"
    detail = requested.json()
    resolved = await approve(client, detail)
    assert resolved["status"] == "APPROVED"

    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"
    session_count = len(detail["result"]["sessions"])
    assert done.json()["result_payload"]["created_count"] == session_count
    assert done.json()["result_payload"]["failed_count"] == 0

    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(ExternalArtifact))
        ) == session_count

    again = await client.post(path + "/execute")
    assert again.json()["result_payload"] == done.json()["result_payload"]
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(ExternalArtifact))
        ) == session_count
        assert (await session.scalar(select(func.count()).select_from(LocalExecution))) == 1

    events = (await client.get(f"/workflow-runs/{done.json()['id']}/events")).json()
    assert [
        e["event_metadata"]["to"] for e in events if e["event_type"] == "WORKFLOW_STATE_CHANGED"
    ] == [
        "ANALYZING",
        "PLAN_READY",
        "AWAITING_APPROVAL",
        "APPROVED",
        "QUEUED",
        "EXECUTING",
        "COMPLETED",
    ]


async def test_partial_failure_preserves_successful_artifacts(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    path, detail = await ready(
        client,
        session_factory,
        account,
        encryption_key,
        tasks=[
            task_payload("essay", deadline="2026-01-08T17:00:00+00:00", minutes=60),
            task_payload("lab", deadline="2026-01-09T17:00:00+00:00", minutes=60),
        ],
    )
    monkeypatch.setattr(
        GoogleCalendarApiClient, "create_event", fake_create_event(fail_ids={"lab"})
    )
    requested = await client.post(path + "/approval")
    assert requested.status_code == 200, requested.text
    detail = requested.json()
    await approve(client, detail)

    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "PARTIALLY_COMPLETED"
    payload = done.json()["result_payload"]
    assert payload["created_count"] == 1
    assert payload["failed_count"] == 1
    assert done.json()["error_code"] == "CALENDAR_RATE_LIMITED"

    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(ExternalArtifact))) == 1

    events = (await client.get(f"/workflow-runs/{done.json()['id']}/events")).json()
    assert any(e["event_type"] == "CALENDAR_EVENT_CREATE_FAILED" for e in events)
    assert not any(e["event_type"] == "WORKFLOW_COMPLETED" for e in events)

    assert (await client.post(path + "/execute")).status_code == 409


async def test_no_bypass_without_approval(
    client, account, session_factory, encryption_key, monkeypatch
):
    monkeypatch.setattr(GoogleCalendarApiClient, "busy_intervals", no_busy_intervals)
    path, detail = await ready(client, session_factory, account, encryption_key)
    assert (await client.post(path + "/execute")).status_code == 409


async def test_import_tasks_uses_default_notion_task_database(
    client, account, session_factory, encryption_key, monkeypatch
):
    from app.connectors.notion.client import NotionApiClient
    from app.connectors.notion.schemas import NotionTaskDatabase
    from app.connectors.notion.service import NotionTaskSourceService
    from app.connectors.notion.tasks import NotionTaskPropertyMapping
    from app.infrastructure.credentials import FernetCredentialStore
    from app.repositories.relay import RelayRepository

    store = FernetCredentialStore([encryption_key])
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=UUID(account["id"]),
                provider=Provider.NOTION,
                external_account_id="workspace-1",
                display_name="Student Workspace",
                access_token_encrypted=store.encrypt("notion-token"),
                scopes=["read_content", "insert_content"],
                provider_metadata={"workspace_id": "workspace-1"},
                status="CONNECTED",
            )
        )
        await session.commit()

        class FakeClient:
            async def search_databases(self):
                return [NotionTaskDatabase(id="db-1", title="Assignments")]

        class Service(NotionTaskSourceService):
            async def client(self, connection):
                return FakeClient()

        service = Service(RelayRepository(session), store)
        owner = UUID(account["id"])
        await service.refresh(owner)
        await service.select(
            owner,
            "db-1",
            NotionTaskPropertyMapping(
                title="Task Name",
                deadline="Due Date",
                estimated_minutes="Estimated Hours",
                estimate_unit="hours",
            ),
        )

    async def fake_query_database(self, database_id):
        assert database_id == "db-1"
        return [
            {
                "id": "page-1",
                "properties": {
                    "Task Name": {"type": "title", "title": [{"plain_text": "Homework"}]},
                    "Due Date": {
                        "type": "date",
                        "date": {"start": "2026-01-08T17:00:00-05:00"},
                    },
                    "Estimated Hours": {"type": "number", "number": 2},
                },
            }
        ]

    monkeypatch.setattr(NotionApiClient, "query_database", fake_query_database)
    await connect_google(session_factory, account, encryption_key)
    path, detail = await start_and_setup(client, tasks=[])
    imported = await client.post(path + "/tasks/import")
    assert imported.status_code == 200, imported.text
    tasks = imported.json()["setup"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Homework"
    assert tasks[0]["estimated_minutes"] == 120
