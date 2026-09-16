from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.domain.enums import ConnectionStatus, Provider
from app.models.entities import ConnectedAccount


async def _project(client, **extra):
    response = await client.post(
        "/projects",
        json={"name": "Launch", "space": "WORK", **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _task(client, project_id, title, due_days=3, estimate=60):
    response = await client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": title,
            "due_date": (datetime.now(UTC) + timedelta(days=due_days)).isoformat(),
            "estimate_minutes": estimate,
            "priority": "HIGH",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_project_tasks_feed_week_plan_without_duplicate_task_store(client, account):
    project = await _project(client)
    first = await _task(client, project["id"], "Write launch notes", 2, 45)
    second = await _task(client, project["id"], "Review launch checklist", 5, 90)
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    response = await client.post(
        f"/projects/{project['id']}/plan",
        json={
            "task_ids": [first["id"], second["id"]],
            "start": start.isoformat(),
            "end": (start + timedelta(days=7)).isoformat(),
            "calendar_id": None,
        },
    )

    assert response.status_code == 201, response.text
    detail = response.json()
    assert {item["id"] for item in detail["setup"]["tasks"]} == {
        first["id"],
        second["id"],
    }
    assert detail["result"]["sessions"]
    assert len((await client.get(f"/projects/{project['id']}/tasks")).json()) == 2

    approval = await client.post(f"/workflows/plan/{detail['run']['id']}/approval")
    assert approval.status_code == 409
    assert approval.json()["code"] == "CALENDAR_DESTINATION_REQUIRED"
    assert "select a calendar" in approval.json()["message"].lower()


async def test_task_without_due_date_or_estimate_is_not_schedulable(client, account):
    project = await _project(client)
    response = await client.post(
        f"/projects/{project['id']}/tasks", json={"title": "Ambiguous task"}
    )
    task = response.json()
    start = datetime.now(UTC)
    planned = await client.post(
        f"/projects/{project['id']}/plan",
        json={
            "task_ids": [task["id"]],
            "start": start.isoformat(),
            "end": (start + timedelta(days=7)).isoformat(),
            "calendar_id": None,
        },
    )
    assert planned.status_code == 422


async def test_task_can_be_edited_later_and_become_schedulable(client, account):
    project = await _project(client)
    created = await client.post(f"/projects/{project['id']}/tasks", json={"title": "Plan later"})
    task = created.json()
    due = datetime.now(UTC) + timedelta(days=4)
    updated = await client.put(
        f"/projects/{project['id']}/tasks/{task['id']}",
        json={
            "title": "Plan this week",
            "description": "Edited after capture",
            "due_date": due.isoformat(),
            "estimate_minutes": 75,
            "priority": "MEDIUM",
            "status": "IN_PROGRESS",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["due_date"] is not None
    assert updated.json()["estimate_minutes"] == 75
    assert updated.json()["status"] == "IN_PROGRESS"
    all_tasks = await client.get("/tasks")
    assert [item["id"] for item in all_tasks.json()] == [task["id"]]

    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    planned = await client.post(
        f"/projects/{project['id']}/plan",
        json={
            "task_ids": [task["id"]],
            "start": start.isoformat(),
            "end": (start + timedelta(days=7)).isoformat(),
            "calendar_id": None,
        },
    )
    assert planned.status_code == 201, planned.text


async def test_github_issue_requires_selected_repository(client, account):
    project = await _project(client)
    task = await _task(client, project["id"], "Ship API")
    response = await client.post(
        f"/projects/{project['id']}/tasks/{task['id']}/github-issue/preview",
        json={"title": task["title"], "description": "Ready to implement."},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "GITHUB_REPOSITORY_NOT_FOUND"


async def test_github_issue_preview_confirm_and_deduplicate(
    client, account, session_factory, monkeypatch
):
    monkeypatch.setattr(get_settings(), "github_publish_mode", "mock")
    project = await _project(client, github_repository_owner="relay", github_repository_name="web")
    task = await _task(client, project["id"], "Ship API")
    async with session_factory() as session:
        session.add(
            ConnectedAccount(
                user_id=account["id"],
                provider=Provider.GITHUB,
                external_account_id="student",
                display_name="student",
                access_token_encrypted=None,
                refresh_token_encrypted=None,
                token_expires_at=None,
                scopes=[],
                provider_metadata={},
                status=ConnectionStatus.CONNECTED,
            )
        )
        await session.commit()

    path = f"/projects/{project['id']}/tasks/{task['id']}/github-issue/preview"
    payload = {"title": "Ship API", "description": "Ready to implement."}
    preview = await client.post(path, json=payload)
    assert preview.status_code == 201, preview.text
    duplicate_preview = await client.post(path, json=payload)
    assert duplicate_preview.json()["run_id"] == preview.json()["run_id"]

    item = preview.json()
    confirmed = await client.post(
        f"/projects/{project['id']}/tasks/{task['id']}/github-issue/"
        f"{item['run_id']}/{item['approval_id']}/confirm"
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "COMPLETED"
    retried = await client.post(
        f"/projects/{project['id']}/tasks/{task['id']}/github-issue/"
        f"{item['run_id']}/{item['approval_id']}/confirm"
    )
    assert retried.status_code == 200
    tasks = (await client.get(f"/projects/{project['id']}/tasks")).json()
    assert len(tasks[0]["external_references"]) == 1
    assert tasks[0]["external_references"][0]["label"].startswith("GitHub #")
