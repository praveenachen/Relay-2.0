from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile

from app.ai.base import LanguageModel
from app.api.dependencies import Repository
from app.api.learn import language_model
from app.auth.users import CurrentUser
from app.connectors.github.service import GitHubService
from app.connectors.notion.service import NotionDestinationService
from app.core.config import get_settings
from app.documents.errors import DocumentTooLarge
from app.documents.service import DocumentService
from app.documents.storage import LocalFileStore
from app.infrastructure.credentials import credential_store
from app.runtime.client import RuntimeClient
from app.runtime.factory import runtime_client as build_runtime_client
from app.schemas.domain import RunRead
from app.services.runtime_execution import RuntimeExecutionService
from app.workflows.project_meeting.analysis import MeetingAnalysisService
from app.workflows.project_meeting.execution import CollaborateExecutionService
from app.workflows.project_meeting.schemas import ActionItemsInput, CreateCollaborateRunInput
from app.workflows.project_meeting.service import ProjectMeetingWorkflowService

router = APIRouter(prefix="/workflows/collaborate", tags=["collaborate"])


def github_service(repo: Repository) -> GitHubService:
    settings = get_settings()
    return GitHubService(
        repo,
        credential_store(),
        api_base_url=settings.github_api_base_url,
        timeout=settings.github_timeout_seconds,
    )


def notion_service(repo: Repository) -> NotionDestinationService:
    settings = get_settings()
    return NotionDestinationService(
        repo,
        credential_store(),
        api_base_url=settings.notion_api_base_url,
        timeout=settings.notion_timeout_seconds,
    )


def service(
    repo: Repository,
    model: Annotated[LanguageModel, Depends(language_model)],
    github: Annotated[GitHubService, Depends(github_service)],
    notion: Annotated[NotionDestinationService, Depends(notion_service)],
) -> ProjectMeetingWorkflowService:
    settings = get_settings()
    return ProjectMeetingWorkflowService(
        repo,
        DocumentService(
            settings.max_upload_size_mb * 1024 * 1024, settings.max_document_characters
        ),
        LocalFileStore(settings.document_storage_path),
        MeetingAnalysisService(model),
        github,
        settings.language_model_provider,
        notion,
    )


def runtime_client(repo: Repository) -> RuntimeClient:
    return build_runtime_client(repo, get_settings(), capabilities=("notion", "github"))


Collaborate = Annotated[ProjectMeetingWorkflowService, Depends(service)]
Runtime = Annotated[RuntimeClient, Depends(runtime_client)]


@router.get("/config")
async def configuration(user: CurrentUser) -> dict[str, str]:
    settings = get_settings()
    return {
        "provider": settings.language_model_provider,
        "notion_publish_mode": settings.notion_publish_mode,
        "github_publish_mode": settings.github_publish_mode,
    }


@router.post("", response_model=RunRead, status_code=201)
async def create(
    data: CreateCollaborateRunInput, user: CurrentUser, collaborate: Collaborate
) -> RunRead:
    return await collaborate.create(user.id, data.project_id)


@router.get("/{run_id}")
async def detail(run_id: UUID, user: CurrentUser, collaborate: Collaborate) -> dict[str, Any]:
    return await collaborate.detail(run_id, user.id)


@router.post("/{run_id}/transcript")
async def upload(
    run_id: UUID, user: CurrentUser, collaborate: Collaborate, file: UploadFile
) -> dict[str, Any]:
    await collaborate.owned_run(run_id, user.id)
    limit = get_settings().max_upload_size_mb * 1024 * 1024
    try:
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise DocumentTooLarge()
        return await collaborate.upload(
            run_id, user.id, file.filename or "", file.content_type or "", content
        )
    finally:
        await file.close()


@router.post("/{run_id}/parse")
async def parse(
    run_id: UUID, user: CurrentUser, collaborate: Collaborate, meeting_date: date | None = None
) -> dict[str, Any]:
    return await collaborate.parse(run_id, user.id, meeting_date=meeting_date)


@router.post("/{run_id}/analyze")
async def analyze(run_id: UUID, user: CurrentUser, collaborate: Collaborate) -> dict[str, Any]:
    return await collaborate.analyze(run_id, user.id)


@router.put("/{run_id}/action-items")
async def update_action_items(
    run_id: UUID, data: ActionItemsInput, user: CurrentUser, collaborate: Collaborate
) -> dict[str, Any]:
    return await collaborate.update_action_items(run_id, user.id, data.action_items)


@router.post("/{run_id}/approval")
async def request_approval(
    run_id: UUID, user: CurrentUser, collaborate: Collaborate
) -> dict[str, Any]:
    return await collaborate.request_approval(run_id, user.id)


@router.post("/{run_id}/execute", response_model=RunRead)
async def execute(
    run_id: UUID, user: CurrentUser, collaborate: Collaborate, runtime: Runtime
) -> RunRead:
    await collaborate.owned_run(run_id, user.id)
    return await CollaborateExecutionService(collaborate.repo, runtime).execute(run_id, user.id)


@router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel(
    run_id: UUID, user: CurrentUser, runtime: Runtime, collaborate: Collaborate
) -> RunRead:
    await collaborate.owned_run(run_id, user.id)
    return await RuntimeExecutionService(collaborate.repo, runtime).cancel(run_id, user.id)
