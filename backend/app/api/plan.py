from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import Repository
from app.api.routes import google_oauth
from app.auth.users import CurrentUser
from app.connectors.google.service import GoogleCalendarService
from app.connectors.notion.service import NotionDestinationService
from app.core.config import get_settings
from app.domain.enums import ApprovalStatus, WorkflowStatus
from app.infrastructure.credentials import credential_store
from app.runtime.client import RuntimeClient
from app.runtime.factory import runtime_client as build_runtime_client
from app.scheduling.models import StudySession
from app.scheduling.service import StudySchedulingService
from app.schemas.domain import RunRead
from app.services.approvals import ApprovalService
from app.services.runtime_execution import RuntimeExecutionService
from app.workflows.study_plan.execution import StudyPlanExecutionService
from app.workflows.study_plan.schemas import (
    LockSessionInput,
    NotionExportInput,
    PlanSetupInput,
    SessionAdjustmentInput,
)
from app.workflows.study_plan.service import StudyPlanWorkflowService

router = APIRouter(prefix="/workflows/plan", tags=["plan"])


def google_service(repo: Repository) -> GoogleCalendarService:
    settings = get_settings()
    return GoogleCalendarService(
        repo,
        credential_store(),
        oauth=google_oauth(),
        api_base_url=settings.google_calendar_api_base_url,
        timeout=settings.google_timeout_seconds,
    )


def notion_service(repo: Repository) -> NotionDestinationService:
    settings = get_settings()
    return NotionDestinationService(
        repo,
        credential_store(),
        api_base_url=settings.notion_api_base_url,
        timeout=settings.notion_timeout_seconds,
    )


def service(repo: Repository) -> StudyPlanWorkflowService:
    return StudyPlanWorkflowService(
        repo,
        StudySchedulingService(),
        google_service(repo),
        notion_service(repo),
    )


def runtime_client(repo: Repository) -> RuntimeClient:
    return build_runtime_client(repo, get_settings(), capabilities=("calendar",))


Plan = Annotated[StudyPlanWorkflowService, Depends(service)]
Runtime = Annotated[RuntimeClient, Depends(runtime_client)]


@router.get("/config")
async def configuration(user: CurrentUser) -> dict[str, str]:
    return {"scheduler": "cp-sat", "calendar_provider": "google"}


@router.post("", response_model=RunRead, status_code=201)
async def create(user: CurrentUser, plan: Plan) -> RunRead:
    return await plan.create(user.id)


@router.get("/{run_id}")
async def detail(run_id: UUID, user: CurrentUser, plan: Plan) -> dict[str, object]:
    return await plan.detail(run_id, user.id)


@router.put("/{run_id}/setup")
async def setup(
    run_id: UUID, data: PlanSetupInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    return await plan.setup(run_id, user.id, data)


@router.put("/{run_id}/generate")
async def generate(
    run_id: UUID, data: PlanSetupInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    return await plan.generate(run_id, user.id, data)


@router.post("/{run_id}/export/notion")
async def export_notion(
    run_id: UUID, data: NotionExportInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    return await plan.export_to_notion(run_id, user.id, data.destination_page_id)


@router.put("/{run_id}/tasks")
async def review_tasks(
    run_id: UUID, data: PlanSetupInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    detail = await plan.setup(run_id, user.id, data)
    return detail


@router.post("/{run_id}/availability")
async def availability(run_id: UUID, user: CurrentUser, plan: Plan) -> dict[str, object]:
    return await plan.load_availability(run_id, user.id)


@router.post("/{run_id}/solve")
async def solve(run_id: UUID, user: CurrentUser, plan: Plan) -> dict[str, object]:
    return await plan.solve(run_id, user.id)


@router.put("/{run_id}/sessions")
async def sessions(
    run_id: UUID, data: SessionAdjustmentInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    return await plan.adjust_sessions(run_id, user.id, data.sessions)


@router.post("/{run_id}/sessions/{session_id}/lock")
async def lock_session(
    run_id: UUID, session_id: str, data: LockSessionInput, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    current = await plan.detail(run_id, user.id)
    setup_payload = current.get("setup") or {}
    sessions = tuple(
        StudySession.model_validate(item).model_copy(
            update={
                "locked": data.locked if item.get("id") == session_id else item.get("locked", False)
            }
        )
        for item in setup_payload.get("sessions", [])
    )
    return await plan.adjust_sessions(run_id, user.id, sessions)


@router.delete("/{run_id}/sessions/{session_id}")
async def remove_session(
    run_id: UUID, session_id: str, user: CurrentUser, plan: Plan
) -> dict[str, object]:
    current = await plan.detail(run_id, user.id)
    setup_payload = current.get("setup") or {}
    sessions = tuple(
        StudySession.model_validate(item)
        for item in setup_payload.get("sessions", [])
        if item.get("id") != session_id
    )
    return await plan.adjust_sessions(run_id, user.id, sessions)


@router.post("/{run_id}/approval")
async def request_approval(run_id: UUID, user: CurrentUser, plan: Plan) -> dict[str, object]:
    return await plan.request_approval(run_id, user.id)


@router.post("/{run_id}/execute", response_model=RunRead)
async def execute(run_id: UUID, user: CurrentUser, plan: Plan, runtime: Runtime) -> RunRead:
    await plan.owned_run(run_id, user.id)
    return await StudyPlanExecutionService(plan.repo, runtime).execute(run_id, user.id)


@router.post("/{run_id}/approve-and-execute", response_model=RunRead)
async def approve_and_execute(
    run_id: UUID, user: CurrentUser, plan: Plan, runtime: Runtime
) -> RunRead:
    run = await plan.owned_run(run_id, user.id)
    if run.status == WorkflowStatus.PLAN_READY:
        await plan.request_approval(run_id, user.id)
    approvals = await plan.repo.run_approvals(run_id)
    pending = next((item for item in approvals if item.status == ApprovalStatus.PENDING), None)
    if pending is not None:
        await ApprovalService(plan.repo).resolve(
            pending.id, user.id, pending.original_payload, approve=True
        )
    return await StudyPlanExecutionService(plan.repo, runtime).execute(run_id, user.id)


@router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel(run_id: UUID, user: CurrentUser, runtime: Runtime, plan: Plan) -> RunRead:
    await plan.owned_run(run_id, user.id)
    return await RuntimeExecutionService(plan.repo, runtime).cancel(run_id, user.id)
