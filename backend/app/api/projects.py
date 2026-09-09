from uuid import UUID

from fastapi import APIRouter, Response

from app.api.dependencies import Repository
from app.auth.users import CurrentUser
from app.schemas.domain import ProjectInput, ProjectMemberInput, ProjectMemberRead, ProjectRead
from app.services.projects import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(user: CurrentUser, repo: Repository) -> list[ProjectRead]:
    return await ProjectService(repo).list_projects(user.id)


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(data: ProjectInput, user: CurrentUser, repo: Repository) -> ProjectRead:
    return await ProjectService(repo).create(user.id, data)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: UUID, user: CurrentUser, repo: Repository) -> ProjectRead:
    return await ProjectService(repo).get(user.id, project_id)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID, data: ProjectInput, user: CurrentUser, repo: Repository
) -> ProjectRead:
    return await ProjectService(repo).update(user.id, project_id, data)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
async def list_members(
    project_id: UUID, user: CurrentUser, repo: Repository
) -> list[ProjectMemberRead]:
    return await ProjectService(repo).members(user.id, project_id)


@router.post("/{project_id}/members", response_model=ProjectMemberRead, status_code=201)
async def add_member(
    project_id: UUID, data: ProjectMemberInput, user: CurrentUser, repo: Repository
) -> ProjectMemberRead:
    return await ProjectService(repo).add_member(user.id, project_id, data)


@router.put("/{project_id}/members/{member_id}", response_model=ProjectMemberRead)
async def update_member(
    project_id: UUID,
    member_id: UUID,
    data: ProjectMemberInput,
    user: CurrentUser,
    repo: Repository,
) -> ProjectMemberRead:
    return await ProjectService(repo).update_member(user.id, project_id, member_id, data)


@router.delete("/{project_id}/members/{member_id}", status_code=204)
async def remove_member(
    project_id: UUID, member_id: UUID, user: CurrentUser, repo: Repository
) -> Response:
    await ProjectService(repo).remove_member(user.id, project_id, member_id)
    return Response(status_code=204)
