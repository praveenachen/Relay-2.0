from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from app.ai.base import LanguageModel
from app.ai.fake import FakeLanguageModel
from app.ai.openai import OpenAIProvider
from app.api.dependencies import Repository
from app.auth.users import CurrentUser
from app.core.config import get_settings
from app.documents.errors import DocumentTooLarge
from app.documents.service import DocumentService
from app.documents.storage import LocalFileStore
from app.runtime.client import RuntimeClient
from app.runtime.factory import runtime_client as build_runtime_client
from app.schemas.domain import RunRead
from app.services.execution import ExecutionService
from app.services.runtime_execution import RuntimeExecutionService
from app.workflows.lecture_notes.schemas import LectureSummary, StrictModel
from app.workflows.lecture_notes.service import LectureNotesWorkflowService
from app.workflows.lecture_notes.summarization import SummaryService

router = APIRouter(prefix="/workflows/learn", tags=["learn"])


def language_model() -> LanguageModel:
    settings = get_settings()
    if settings.language_model_provider == "fake":
        return FakeLanguageModel()
    return OpenAIProvider(
        settings.openai_api_key.get_secret_value(),
        settings.openai_model,
        settings.model_timeout_seconds,
    )


def service(
    repo: Repository,
    model: Annotated[LanguageModel, Depends(language_model)],
) -> LectureNotesWorkflowService:
    settings = get_settings()
    return LectureNotesWorkflowService(
        repo,
        DocumentService(
            settings.max_upload_size_mb * 1024 * 1024, settings.max_document_characters
        ),
        LocalFileStore(settings.document_storage_path),
        SummaryService(
            model, settings.max_direct_summary_tokens, settings.max_section_summary_tokens
        ),
        settings.language_model_provider,
    )


def runtime_client(repo: Repository) -> RuntimeClient:
    return build_runtime_client(repo, get_settings())


Learn = Annotated[LectureNotesWorkflowService, Depends(service)]
Runtime = Annotated[RuntimeClient, Depends(runtime_client)]


class SummaryEdit(StrictModel):
    summary: LectureSummary
    expected_payload: dict[str, Any]


@router.get("/config")
async def configuration(user: CurrentUser) -> dict[str, Any]:
    settings = get_settings()
    return {
        "max_upload_bytes": settings.max_upload_size_mb * 1024 * 1024,
        "provider": settings.language_model_provider,
        "notion_publish_mode": settings.notion_publish_mode,
    }


@router.post("", response_model=RunRead, status_code=201)
async def create(user: CurrentUser, learn: Learn) -> RunRead:
    return await learn.create(user.id)


@router.get("/{run_id}")
async def detail(run_id: UUID, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.detail(run_id, user.id)


@router.post("/{run_id}/documents")
async def upload(run_id: UUID, user: CurrentUser, learn: Learn, file: UploadFile) -> dict[str, Any]:
    await learn.owned_run(run_id, user.id)
    limit = get_settings().max_upload_size_mb * 1024 * 1024
    try:
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise DocumentTooLarge()
        return await learn.upload(
            run_id,
            user.id,
            file.filename or "",
            file.content_type or "",
            content,
        )
    finally:
        await file.close()


@router.get("/{run_id}/document")
async def document(run_id: UUID, user: CurrentUser, learn: Learn) -> Response:
    source = await learn.source(run_id, user.id)
    return Response(
        await learn.store.read(source.storage_key),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="lecture-source"'},
    )


@router.get("/{run_id}/artifact")
async def artifact(run_id: UUID, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.artifact(run_id, user.id)


@router.post("/{run_id}/parse")
async def parse(run_id: UUID, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.parse(run_id, user.id)


@router.post("/{run_id}/summarize")
async def summarize(run_id: UUID, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.summarize(run_id, user.id)


@router.put("/{run_id}/summary")
async def edit(run_id: UUID, data: SummaryEdit, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.edit(run_id, user.id, data.summary, data.expected_payload)


@router.put("/{run_id}/destination")
async def destination(run_id: UUID, user: CurrentUser, learn: Learn) -> dict[str, Any]:
    return await learn.update_destination(run_id, user.id)


@router.post("/{run_id}/execute", response_model=RunRead)
async def execute(run_id: UUID, user: CurrentUser, learn: Learn, runtime: Runtime) -> RunRead:
    await learn.owned_run(run_id, user.id)
    return await ExecutionService(learn.repo, runtime).execute(run_id, user.id)


@router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel(run_id: UUID, user: CurrentUser, runtime: Runtime, learn: Learn) -> RunRead:
    await learn.owned_run(run_id, user.id)
    return await RuntimeExecutionService(learn.repo, runtime).cancel(run_id, user.id)
