from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import Repository
from app.api.plan import service as plan_service
from app.auth.users import CurrentUser
from app.core.config import get_settings
from app.projects.github_issues import ProjectGitHubIssueService
from app.projects.planning import ProjectPlanningService
from app.projects.schemas import (
    GitHubIssuePreview,
    GitHubIssuePreviewInput,
    ProjectPlanInput,
    ScheduledBlockRead,
)
from app.runtime.client import RuntimeClient
from app.runtime.factory import runtime_client as build_runtime_client
from app.schemas.domain import RunRead
from app.workflows.study_plan.service import StudyPlanWorkflowService

router = APIRouter(tags=["project planning"])


def planner(repo: Repository) -> StudyPlanWorkflowService:
    return plan_service(repo)


def external_runtime(repo: Repository) -> RuntimeClient:
    return build_runtime_client(repo, get_settings(), capabilities=("github",))


Planner = Annotated[StudyPlanWorkflowService, Depends(planner)]
Runtime = Annotated[RuntimeClient, Depends(external_runtime)]


@router.post("/projects/{project_id}/plan", status_code=201)
async def create_project_plan(
    project_id: UUID,
    data: ProjectPlanInput,
    user: CurrentUser,
    repo: Repository,
    plan: Planner,
) -> dict[str, object]:
    return await ProjectPlanningService(repo, plan).generate(project_id, user.id, data)


@router.get("/schedule", response_model=list[ScheduledBlockRead])
async def schedule(user: CurrentUser, repo: Repository, plan: Planner) -> list[ScheduledBlockRead]:
    return await ProjectPlanningService(repo, plan).scheduled_blocks(user.id)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/github-issue/preview",
    response_model=GitHubIssuePreview,
    status_code=201,
)
async def preview_github_issue(
    project_id: UUID,
    task_id: UUID,
    data: GitHubIssuePreviewInput,
    user: CurrentUser,
    repo: Repository,
    runtime: Runtime,
) -> GitHubIssuePreview:
    return await ProjectGitHubIssueService(repo, runtime).preview(
        project_id, task_id, user.id, data
    )


@router.post(
    "/projects/{project_id}/tasks/{task_id}/github-issue/{run_id}/{approval_id}/confirm",
    response_model=RunRead,
)
async def confirm_github_issue(
    project_id: UUID,
    task_id: UUID,
    run_id: UUID,
    approval_id: UUID,
    user: CurrentUser,
    repo: Repository,
    runtime: Runtime,
) -> RunRead:
    await repo.task(project_id, task_id, user.id)
    return await ProjectGitHubIssueService(repo, runtime).confirm(run_id, approval_id, user.id)
