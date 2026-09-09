from uuid import UUID

import pytest
from conftest import login, register
from sqlalchemy import select

from app.domain.enums import ActionProvider
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import ApprovalRequired
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ProposedAction,
    WorkflowDefinition,
)
from app.repositories.relay import RelayRepository
from app.services.workflows import WorkflowService


async def create_run(client):
    definitions = (await client.get("/workflow-definitions")).json()
    response = await client.post(
        "/workflow-runs", json={"workflow_definition_id": definitions[0]["id"]}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def proposed(client, session_factory, owner, count=1):
    run = await create_run(client)
    async with session_factory() as session:
        service = WorkflowService(RelayRepository(session))
        for status in [S.ANALYZING, S.PLAN_READY]:
            await service.transition_workflow(UUID(run["id"]), status, UUID(owner["id"]))
        for index in range(count):
            session.add(
                ProposedAction(
                    workflow_run_id=UUID(run["id"]),
                    provider=ActionProvider.NOTION,
                    action_type="test_proposal",
                    payload={"title": f"Example {index}", "nested": {"items": [1, True, None]}},
                )
            )
        await session.commit()
        await service.request_approvals(UUID(run["id"]), UUID(owner["id"]))
    return run, (await client.get("/approvals")).json()


async def test_draft_creation_and_filters(client, account):
    run = await create_run(client)
    assert run["status"] == "DRAFT"
    assert run["started_at"] is None
    assert (await client.get("/workflow-runs", params={"status": "DRAFT"})).json()[0]["id"] == run[
        "id"
    ]
    assert (await client.get("/workflow-runs", params={"status": "COMPLETED"})).json() == []
    events = (await client.get(f"/workflow-runs/{run['id']}/events")).json()
    assert [event["event_type"] for event in events] == ["WORKFLOW_CREATED"]
    bad = await client.post(
        "/workflow-runs",
        json={"workflow_definition_id": run["workflow_definition_id"], "status": "COMPLETED"},
    )
    assert bad.status_code == 422


async def test_disabled_definition(client, account, session_factory):
    definitions = (await client.get("/workflow-definitions")).json()
    async with session_factory() as session:
        definition = await session.get(WorkflowDefinition, UUID(definitions[0]["id"]))
        definition.enabled = False
        await session.commit()
    assert (
        await client.post("/workflow-runs", json={"workflow_definition_id": definitions[0]["id"]})
    ).status_code == 409


async def test_transition_audit_and_approval_guard(client, account, session_factory):
    run = await create_run(client)
    async with session_factory() as session:
        service = WorkflowService(RelayRepository(session))
        result = await service.transition_workflow(
            UUID(run["id"]), S.ANALYZING, UUID(account["id"])
        )
        assert result.started_at is not None
        await service.transition_workflow(UUID(run["id"]), S.PLAN_READY, UUID(account["id"]))
        with pytest.raises(ApprovalRequired):
            await service.transition_workflow(
                UUID(run["id"]), S.AWAITING_APPROVAL, UUID(account["id"])
            )
        await session.rollback()
    events = (await client.get(f"/workflow-runs/{run['id']}/events")).json()
    assert [e["event_type"] for e in events].count("WORKFLOW_STATE_CHANGED") == 2


async def test_exact_approval_and_double_resolution(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account, count=2)
    approval = approvals[0]
    path = f"/approvals/{approval['id']}/approve"
    assert (
        await client.post(path, json={"approved_payload": {"title": "changed"}})
    ).status_code == 409
    response = await client.post(path, json={"approved_payload": approval["original_payload"]})
    assert response.status_code == 200, response.text
    assert response.json()["approved_payload"] == approval["original_payload"]
    assert (await client.get(f"/workflow-runs/{run['id']}")).json()["status"] == "AWAITING_APPROVAL"
    assert (
        await client.post(path, json={"approved_payload": approval["original_payload"]})
    ).status_code == 409
    other = approvals[1]
    assert (
        await client.post(
            f"/approvals/{other['id']}/approve",
            json={"approved_payload": other["original_payload"]},
        )
    ).status_code == 200
    assert (await client.get(f"/workflow-runs/{run['id']}")).json()["status"] == "APPROVED"
    async with session_factory() as session:
        stored = await session.get(ApprovalRequest, UUID(approval["id"]))
        assert stored.approved_payload == approval["original_payload"]
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "ACTION_APPROVED")
            )
        ).all()
        assert len(events) == 2


async def test_rejection_expires_remaining_requests(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account, count=2)
    path = f"/approvals/{approvals[0]['id']}/reject"
    assert (await client.post(path)).status_code == 200
    assert (await client.post(path)).status_code == 409
    assert (await client.get(f"/workflow-runs/{run['id']}")).json()["status"] == "REJECTED"
    other = (await client.get(f"/approvals/{approvals[1]['id']}")).json()
    assert other["status"] == "EXPIRED"
    assert other["approved_payload"] is None


async def test_cross_user_runs_approvals_preferences(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account)
    old_preferences = (await client.get("/preferences")).json()
    await client.post("/auth/logout")
    await register(client, "other@example.com")
    await login(client, "other@example.com")
    for path in [
        f"/workflow-runs/{run['id']}",
        f"/workflow-runs/{run['id']}/events",
        f"/approvals/{approvals[0]['id']}",
    ]:
        assert (await client.get(path)).status_code == 404
    assert (
        await client.post(
            f"/approvals/{approvals[0]['id']}/approve",
            json={"approved_payload": approvals[0]["original_payload"]},
        )
    ).status_code == 404
    assert (await client.get("/workflow-runs")).json() == []
    assert (await client.get("/approvals")).json() == []
    own = (await client.get("/preferences")).json()
    assert own["user_id"] != old_preferences["user_id"]
    own["user_id"] = old_preferences["user_id"]
    assert (await client.put("/preferences", json=own)).status_code == 422
    assert (await client.get(f"/preferences/{old_preferences['id']}")).status_code == 404


async def test_preference_validation_and_audit(client, account):
    value = (await client.get("/preferences")).json()
    value.pop("id")
    value.pop("user_id")
    value["timezone"] = "America/Toronto"
    assert (await client.put("/preferences", json=value)).status_code == 200
    value["preferred_session_minutes"] = 100
    value["maximum_session_minutes"] = 10
    assert (await client.put("/preferences", json=value)).status_code == 422
    assert (await client.get("/preferences")).json()["preferred_session_minutes"] == 50
