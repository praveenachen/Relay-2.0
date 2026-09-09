from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import Repository
from app.auth.users import CurrentUser, UserRead
from app.domain.enums import ApprovalStatus, Provider, WorkflowStatus
from app.schemas.domain import (
    ApprovalInput,
    ApprovalRead,
    AuditRead,
    ConnectionRead,
    DefinitionRead,
    PreferenceInput,
    PreferenceRead,
    ProfileInput,
    RunInput,
    RunRead,
)
from app.services.approvals import ApprovalService
from app.services.connections import ConnectionService
from app.services.preferences import PreferenceService
from app.services.workflows import WorkflowService

router = APIRouter()
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/users/me", response_model=UserRead, tags=["account"])
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/users/me", response_model=UserRead, tags=["account"])
async def profile(data: ProfileInput, user: CurrentUser, repo: Repository) -> UserRead:
    await PreferenceService(repo).profile(user, data)
    return UserRead.model_validate(user)


@router.post("/users/me/onboarding", status_code=204, tags=["account"])
async def finish_onboarding(user: CurrentUser, repo: Repository) -> Response:
    await PreferenceService(repo).finish_onboarding(user)
    return Response(status_code=204)


@router.get("/preferences", response_model=PreferenceRead, tags=["account"])
async def preferences(user: CurrentUser, repo: Repository) -> PreferenceRead:
    return PreferenceRead.model_validate(await repo.preferences(user.id))


@router.put("/preferences", response_model=PreferenceRead, tags=["account"])
async def update_preferences(
    data: PreferenceInput, user: CurrentUser, repo: Repository
) -> PreferenceRead:
    return await PreferenceService(repo).update(user.id, data)


@router.get("/workflow-definitions", response_model=list[DefinitionRead], tags=["workflows"])
async def definitions(user: CurrentUser, repo: Repository) -> list[DefinitionRead]:
    return [DefinitionRead.model_validate(item) for item in await repo.definitions()]


@router.get("/workflow-runs", response_model=list[RunRead], tags=["workflows"])
async def runs(
    user: CurrentUser,
    repo: Repository,
    status: WorkflowStatus | None = None,
    workflow_definition_id: UUID | None = None,
    created_since: datetime | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[RunRead]:
    return [
        RunRead.model_validate(item)
        for item in await repo.runs(
            user.id, status, workflow_definition_id, created_since, limit, offset
        )
    ]


@router.post("/workflow-runs", response_model=RunRead, status_code=201, tags=["workflows"])
async def create_run(data: RunInput, user: CurrentUser, repo: Repository) -> RunRead:
    return await WorkflowService(repo).create(user.id, data)


@router.get("/workflow-runs/{run_id}", response_model=RunRead, tags=["workflows"])
async def get_run(run_id: UUID, user: CurrentUser, repo: Repository) -> RunRead:
    return RunRead.model_validate(await repo.run(run_id, user.id))


@router.get("/workflow-runs/{run_id}/events", response_model=list[AuditRead], tags=["workflows"])
async def events(run_id: UUID, user: CurrentUser, repo: Repository) -> list[AuditRead]:
    return [AuditRead.model_validate(item) for item in await repo.events(run_id, user.id)]


@router.get("/approvals", response_model=list[ApprovalRead], tags=["approvals"])
async def approvals(
    user: CurrentUser,
    repo: Repository,
    status: ApprovalStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[ApprovalRead]:
    return [
        ApprovalRead.model_validate(item)
        for item in await repo.approvals(user.id, status, limit, offset)
    ]


@router.get("/approvals/{approval_id}", response_model=ApprovalRead, tags=["approvals"])
async def get_approval(approval_id: UUID, user: CurrentUser, repo: Repository) -> ApprovalRead:
    return ApprovalRead.model_validate(await repo.approval(approval_id, user.id))


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRead, tags=["approvals"])
async def approve(
    approval_id: UUID, data: ApprovalInput, user: CurrentUser, repo: Repository
) -> ApprovalRead:
    return await ApprovalService(repo).resolve(
        approval_id, user.id, data.approved_payload, approve=True
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRead, tags=["approvals"])
async def reject(approval_id: UUID, user: CurrentUser, repo: Repository) -> ApprovalRead:
    return await ApprovalService(repo).resolve(approval_id, user.id, None, approve=False)


@router.get("/connections", response_model=list[ConnectionRead], tags=["connections"])
async def connections(user: CurrentUser, repo: Repository) -> list[ConnectionRead]:
    return [ConnectionRead.model_validate(item) for item in await repo.connections(user.id)]


@router.get("/connections/{provider}", response_model=list[ConnectionRead], tags=["connections"])
async def provider_connections(
    provider: Provider, user: CurrentUser, repo: Repository
) -> list[ConnectionRead]:
    return [
        ConnectionRead.model_validate(item) for item in await repo.connections(user.id, provider)
    ]


@router.delete("/connections/{provider}", status_code=204, tags=["connections"])
async def disconnect(provider: Provider, user: CurrentUser, repo: Repository) -> Response:
    await ConnectionService(repo).disconnect(user.id, provider)
    return Response(status_code=204)


@router.get("/connections/{provider}/authorize", tags=["connections"])
async def authorize(provider: Provider, user: CurrentUser, repo: Repository) -> None:
    ConnectionService(repo).authorize(provider)


@router.get("/connections/{provider}/callback", tags=["connections"])
async def callback(provider: Provider, user: CurrentUser, repo: Repository) -> None:
    ConnectionService(repo).callback(provider)
