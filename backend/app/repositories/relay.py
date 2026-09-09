from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ApprovalStatus, Provider, WorkflowStatus
from app.domain.errors import ApprovalNotFound, UnauthorizedResourceAccess, WorkflowNotFound
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ConnectedAccount,
    ProposedAction,
    UserPreference,
    WorkflowDefinition,
    WorkflowRun,
)


class RelayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, run_id: UUID, owner: UUID, *, lock: bool = False) -> WorkflowRun:
        query = select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.user_id == owner)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        run = await self.session.scalar(query)
        if run is None:
            raise WorkflowNotFound()
        return run

    async def approval(self, approval_id: UUID, owner: UUID) -> ApprovalRequest:
        approval = await self.session.scalar(
            select(ApprovalRequest)
            .join(WorkflowRun, WorkflowRun.id == ApprovalRequest.workflow_run_id)
            .where(ApprovalRequest.id == approval_id, WorkflowRun.user_id == owner)
        )
        if approval is None:
            raise ApprovalNotFound()
        return approval

    async def preferences(self, owner: UUID) -> UserPreference:
        item = await self.session.scalar(
            select(UserPreference).where(UserPreference.user_id == owner)
        )
        if item is None:
            raise UnauthorizedResourceAccess()
        return item

    async def definitions(self) -> Sequence[WorkflowDefinition]:
        return (
            await self.session.scalars(select(WorkflowDefinition).order_by(WorkflowDefinition.id))
        ).all()

    async def runs(
        self,
        owner: UUID,
        status: WorkflowStatus | None = None,
        definition_id: UUID | None = None,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WorkflowRun]:
        query = select(WorkflowRun).where(WorkflowRun.user_id == owner)
        if status is not None:
            query = query.where(WorkflowRun.status == status)
        if definition_id is not None:
            query = query.where(WorkflowRun.workflow_definition_id == definition_id)
        if since is not None:
            query = query.where(WorkflowRun.created_at >= since)
        return (
            await self.session.scalars(
                query.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()

    async def approvals(
        self, owner: UUID, status: ApprovalStatus | None = None, limit: int = 50, offset: int = 0
    ) -> Sequence[ApprovalRequest]:
        query = select(ApprovalRequest).join(WorkflowRun).where(WorkflowRun.user_id == owner)
        if status is not None:
            query = query.where(ApprovalRequest.status == status)
        return (
            await self.session.scalars(
                query.order_by(ApprovalRequest.requested_at.desc()).limit(limit).offset(offset)
            )
        ).all()

    async def actions(self, run_id: UUID) -> Sequence[ProposedAction]:
        return (
            await self.session.scalars(
                select(ProposedAction).where(ProposedAction.workflow_run_id == run_id)
            )
        ).all()

    async def run_approvals(self, run_id: UUID) -> Sequence[ApprovalRequest]:
        return (
            await self.session.scalars(
                select(ApprovalRequest).where(ApprovalRequest.workflow_run_id == run_id)
            )
        ).all()

    async def connections(
        self, owner: UUID, provider: Provider | None = None, *, lock: bool = False
    ) -> Sequence[ConnectedAccount]:
        query = select(ConnectedAccount).where(ConnectedAccount.user_id == owner)
        if provider is not None:
            query = query.where(ConnectedAccount.provider == provider)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return (await self.session.scalars(query.order_by(ConnectedAccount.created_at))).all()

    async def events(self, run_id: UUID, owner: UUID) -> Sequence[AuditEvent]:
        await self.run(run_id, owner)
        return (
            await self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.workflow_run_id == run_id, AuditEvent.user_id == owner)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        ).all()
