from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from test_application import proposed

from app.domain.enums import WorkflowStatus
from app.domain.errors import ApprovalAlreadyResolved, DomainError
from app.models.entities import (
    AccessToken,
    ApprovalRequest,
    AuditEvent,
    ProposedAction,
    WorkflowRun,
)


async def test_stale_proposal_and_wrong_workflow_state(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account)
    approval = approvals[0]
    async with session_factory() as session:
        action = await session.get(ProposedAction, UUID(approval["proposed_action_id"]))
        action.payload = {"changed": True}
        await session.commit()
    response = await client.post(
        f"/approvals/{approval['id']}/approve",
        json={"approved_payload": approval["original_payload"]},
    )
    assert response.status_code == 409
    async with session_factory() as session:
        action = await session.get(ProposedAction, UUID(approval["proposed_action_id"]))
        action.payload = approval["original_payload"]
        row = await session.get(WorkflowRun, UUID(run["id"]))
        row.status = WorkflowStatus.CANCELLED
        await session.commit()
    assert (await client.post(f"/approvals/{approval['id']}/reject")).status_code == 409


async def test_resolved_snapshot_and_audit_cannot_be_edited(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account)
    approval = approvals[0]
    await client.post(
        f"/approvals/{approval['id']}/approve",
        json={"approved_payload": approval["original_payload"]},
    )
    async with session_factory() as session:
        stored = await session.get(ApprovalRequest, UUID(approval["id"]))
        stored.approved_payload = {"tampered": True}
        with pytest.raises(ApprovalAlreadyResolved):
            await session.commit()
        await session.rollback()
        audit = await session.scalar(select(AuditEvent))
        audit.event_type = "TAMPERED"
        with pytest.raises(DomainError):
            await session.commit()
        await session.rollback()


async def test_expired_session_is_rejected(client, account, session_factory):
    async with session_factory() as session:
        token = await session.scalar(select(AccessToken))
        token.created_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()
    assert (await client.get("/users/me")).status_code == 401
