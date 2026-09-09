from copy import deepcopy

import pytest
from conftest import login, register
from sqlalchemy import func, select

from app.ai.fake import FakeLanguageModel
from app.connectors.notion import MockNotionConnector
from app.core.config import get_settings
from app.models.entities import ExternalArtifact, LocalExecution, ProposedAction
from app.workflows.lecture_notes.errors import MalformedModelOutput


@pytest.fixture(autouse=True)
def private_files(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "document_storage_path", tmp_path / "sources")
    monkeypatch.setattr(get_settings(), "language_model_provider", "fake")


async def ready(client):
    created = await client.post("/workflows/learn")
    assert created.status_code == 201, created.text
    path = "/workflows/learn/" + created.json()["id"]
    response = await client.post(
        path + "/documents",
        files={
            "file": (
                "lecture.md",
                b"# Linear Algebra Lecture\nA vector has magnitude and direction."
                b"\n## Eigenvalues\nAn eigenvalue describes scaling.",
                "text/markdown",
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["run"]["status"] == "DRAFT"
    response = await client.post(path + "/parse")
    assert response.status_code == 200, response.text
    response = await client.post(path + "/summarize")
    assert response.status_code == 200, response.text
    return path, response.json()


async def approve(client, detail):
    approval = detail["approval"]
    response = await client.post(
        f"/approvals/{approval['id']}/approve",
        json={
            "approved_payload": approval["original_payload"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_edit_approve_execute_lifecycle(client, account, session_factory):
    path, detail = await ready(client)
    original = deepcopy(detail["approval"]["original_payload"])
    detail["summary"]["title"] = "Week 7 - Eigenvalues"
    edited = await client.put(
        path + "/summary",
        json={
            "summary": detail["summary"],
            "expected_payload": original,
        },
    )
    assert edited.status_code == 200, edited.text
    detail = edited.json()
    assert (
        await client.post(
            f"/approvals/{detail['approval']['id']}/approve",
            json={
                "approved_payload": original,
            },
        )
    ).status_code == 409
    resolved = await approve(client, detail)
    assert resolved["approved_payload"]["title"] == "Week 7 - Eigenvalues"
    assert (
        await client.put(
            path + "/summary",
            json={
                "summary": detail["summary"],
                "expected_payload": detail["approval"]["original_payload"],
            },
        )
    ).status_code == 409
    done = await client.post(path + "/execute")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"
    result = done.json()["result_payload"]["execution"]
    assert result["result"]["title"] == "Week 7 - Eigenvalues"
    assert result["result"]["external_url"].startswith("mock://")
    assert result["completed_at"] and result["started_at"] and result["submitted_at"]
    assert (await client.post(path + "/execute")).json()["result_payload"] == done.json()[
        "result_payload"
    ]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ExternalArtifact)) == 1
        execution = await session.scalar(select(LocalExecution))
        assert execution.request_payload == resolved["approved_payload"]
    events = (await client.get(f"/workflow-runs/{detail['run']['id']}/events")).json()
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
    assert "A vector" not in str([e["event_metadata"] for e in events])


async def test_rejection_and_no_bypass(client, account, session_factory):
    path, detail = await ready(client)
    assert (await client.post(path + "/execute")).status_code == 409
    assert (await client.post(f"/approvals/{detail['approval']['id']}/reject")).status_code == 200
    assert (await client.get(path)).json()["run"]["status"] == "REJECTED"
    assert (await client.post(path + "/execute")).status_code == 409
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LocalExecution)) == 0
        assert await session.scalar(select(func.count()).select_from(ExternalArtifact)) == 0


async def test_malformed_model_fails_before_plan(client, account, monkeypatch, session_factory):
    async def malformed(*args, **kwargs):
        raise MalformedModelOutput()

    monkeypatch.setattr(FakeLanguageModel, "generate_structured", malformed)
    run = (await client.post("/workflows/learn")).json()
    path = f"/workflows/learn/{run['id']}"
    await client.post(path + "/documents", files={"file": ("a.txt", b"A vector.", "text/plain")})
    await client.post(path + "/parse")
    assert (await client.post(path + "/summarize")).status_code == 502
    detail = (await client.get(path)).json()
    assert detail["run"]["status"] == "FAILED" and detail["approval"] is None
    assert detail["run"]["error_code"] == "MALFORMED_MODEL_OUTPUT"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ProposedAction)) == 0
        assert await session.scalar(select(func.count()).select_from(LocalExecution)) == 0
    events = (await client.get(f"/workflow-runs/{run['id']}/events")).json()
    assert any(e["event_type"] == "SUMMARY_GENERATION_FAILED" for e in events)


async def test_mock_failure(client, account, session_factory, monkeypatch):
    path, detail = await ready(client)
    await approve(client, detail)
    original = MockNotionConnector.create_study_page

    async def failure(self, action, idempotency_key):
        return await original(MockNotionConnector(fail=True), action, idempotency_key)

    monkeypatch.setattr(MockNotionConnector, "create_study_page", failure)
    done = await client.post(path + "/execute")
    assert done.json()["status"] == "FAILED"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ExternalArtifact)) == 0
    events = (await client.get(f"/workflow-runs/{detail['run']['id']}/events")).json()
    assert any(e["event_type"] == "EXTERNAL_ACTION_FAILED" for e in events)


async def test_two_user_ownership(client, account):
    path, detail = await ready(client)
    await approve(client, detail)
    await client.post(path + "/execute")
    await client.post("/auth/logout")
    await register(client, "second@example.com")
    await login(client, "second@example.com")
    for endpoint in [
        path,
        path + "/document",
        path + "/artifact",
        f"/workflow-runs/{detail['run']['id']}",
    ]:
        assert (await client.get(endpoint)).status_code == 404
    for endpoint in [path + "/execute", path + "/parse", path + "/summarize"]:
        assert (await client.post(endpoint)).status_code == 404
    assert (
        await client.put(
            path + "/summary",
            json={
                "summary": detail["summary"],
                "expected_payload": detail["approval"]["original_payload"],
            },
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/approvals/{detail['approval']['id']}/approve",
            json={
                "approved_payload": detail["approval"]["original_payload"],
            },
        )
    ).status_code == 404


async def test_duplicate_and_empty_source(client, account):
    run = (await client.post("/workflows/learn")).json()
    path = f"/workflows/learn/{run['id']}"
    files = {"file": ("a.txt", b"  \n", "text/plain")}
    first = await client.post(path + "/documents", files=files)
    second = await client.post(path + "/documents", files=files)
    assert first.json()["source"]["id"] == second.json()["source"]["id"]
    assert (
        await client.post(
            path + "/documents",
            files={
                "file": ("b.txt", b"Different", "text/plain"),
            },
        )
    ).status_code == 409
    assert (await client.post(path + "/parse")).status_code == 422
    assert (await client.get(path)).json()["run"]["status"] == "FAILED"
