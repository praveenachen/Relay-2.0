from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.ai.base import LanguageModel
from app.api.dependencies import Repository
from app.api.learn import language_model
from app.auth.users import CurrentUser
from app.core.config import get_settings
from app.documents.errors import DocumentTooLarge
from app.documents.service import DocumentService
from app.domain.errors import SourceContentRequired
from app.runtime.client import RuntimeClient
from app.runtime.factory import runtime_client as build_runtime_client
from app.sources.analysis import SourceAnalysisService
from app.sources.schemas import (
    SourceCaptureInput,
    SourceRead,
    SourceType,
    TaskExecutionResult,
    TaskProposalEdit,
    TaskProposalRead,
    TaskRead,
)
from app.sources.service import SourceCaptureService, TaskProposalService, task_reads

router = APIRouter(tags=["project sources"])


def capture_service(
    repo: Repository,
    model: Annotated[LanguageModel, Depends(language_model)],
) -> SourceCaptureService:
    return SourceCaptureService(repo, SourceAnalysisService(model))


def task_runtime(repo: Repository) -> RuntimeClient:
    return build_runtime_client(repo, get_settings(), capabilities=())


Capture = Annotated[SourceCaptureService, Depends(capture_service)]
Runtime = Annotated[RuntimeClient, Depends(task_runtime)]


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceRead,
    status_code=201,
)
async def capture_source(
    project_id: UUID,
    user: CurrentUser,
    capture: Capture,
    source_type: Annotated[SourceType, Form()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    content: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> SourceRead:
    original_filename: str | None = None
    source_content = (content or "").strip()
    if file is not None:
        settings = get_settings()
        limit = settings.max_upload_size_mb * 1024 * 1024
        try:
            raw = await file.read(limit + 1)
            if len(raw) > limit:
                raise DocumentTooLarge()
            document_service = DocumentService(limit, settings.max_document_characters)
            uploaded = document_service.validate(
                file.filename or "", file.content_type or "", raw
            )
            parsed = await document_service.parse(uploaded)
            source_content = "\n\n".join(
                (
                    f"{section.heading}\n{section.text}"
                    if section.heading
                    else section.text
                )
                for section in parsed.sections
            )
            original_filename = uploaded.filename
        finally:
            await file.close()
    if not source_content:
        raise SourceContentRequired()
    return await capture.capture(
        project_id,
        user.id,
        user.name,
        SourceCaptureInput(
            source_type=source_type,
            title=title,
            content=source_content,
            original_filename=original_filename,
        ),
    )


@router.get("/projects/{project_id}/sources", response_model=list[SourceRead])
async def sources(
    project_id: UUID, user: CurrentUser, capture: Capture
) -> list[SourceRead]:
    return await capture.list_sources(project_id, user.id)


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
async def project_tasks(
    project_id: UUID, user: CurrentUser, repo: Repository
) -> list[TaskRead]:
    return await task_reads(repo, project_id, user.id)


@router.get("/task-proposals", response_model=list[TaskProposalRead])
async def task_proposals(
    user: CurrentUser, repo: Repository
) -> list[TaskProposalRead]:
    return await TaskProposalService(repo).list(user.id)


@router.put(
    "/task-proposals/{approval_id}", response_model=TaskProposalRead
)
async def edit_task_proposal(
    approval_id: UUID,
    data: TaskProposalEdit,
    user: CurrentUser,
    repo: Repository,
) -> TaskProposalRead:
    return await TaskProposalService(repo).edit(approval_id, user.id, data)


@router.post(
    "/task-proposals/{approval_id}/accept",
    response_model=TaskExecutionResult,
)
async def accept_task_proposal(
    approval_id: UUID,
    data: TaskProposalEdit,
    user: CurrentUser,
    repo: Repository,
    runtime: Runtime,
) -> TaskExecutionResult:
    return await TaskProposalService(repo).accept(
        approval_id, user.id, data, runtime
    )


@router.post(
    "/task-proposals/{approval_id}/reject",
    response_model=dict[str, str],
)
async def reject_task_proposal(
    approval_id: UUID, user: CurrentUser, repo: Repository
) -> dict[str, str]:
    await TaskProposalService(repo).reject(approval_id, user.id)
    return {"status": "rejected"}
