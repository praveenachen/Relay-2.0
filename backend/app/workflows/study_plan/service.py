from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.connectors.google.schemas import CreateCalendarStudyBlockAction
from app.connectors.google.service import GoogleCalendarService
from app.connectors.notion.errors import NotionNotConnected
from app.connectors.notion.service import NotionTaskSourceService
from app.connectors.notion.tasks import NotionTaskMapper, NotionTaskPropertyMapping
from app.domain.enums import (
    ActionProvider,
    ActionStatus,
    ConnectionStatus,
    Provider,
)
from app.domain.enums import WorkflowStatus as S
from app.domain.errors import UnauthorizedResourceAccess
from app.models.entities import ProposedAction, WorkflowDefinition, WorkflowRun
from app.repositories.relay import RelayRepository
from app.scheduling.models import (
    AcademicTask,
    AvailabilityWindow,
    BusyInterval,
    SchedulingProblem,
    SchedulingResult,
    SchedulingStatus,
    StudySession,
)
from app.scheduling.service import StudySchedulingService
from app.schemas.domain import ApprovalRead, RunInput, RunRead
from app.services.audit import record
from app.services.workflows import WorkflowService
from app.workflows.study_plan.actions import OPERATION, CreateCalendarStudyPlanAction
from app.workflows.study_plan.errors import (
    NotionTaskImportEmpty,
    PlanWorkflowInvalidState,
    SchedulingInputInvalid,
)
from app.workflows.study_plan.schemas import PlanSetupInput


class StudyPlanWorkflowService:
    def __init__(
        self,
        repo: RelayRepository,
        scheduler: StudySchedulingService,
        google: GoogleCalendarService,
        notion: NotionTaskSourceService,
    ):
        self.repo = repo
        self.session = repo.session
        self.scheduler = scheduler
        self.google = google
        self.notion = notion
        self.workflow = WorkflowService(repo)

    async def owned_run(self, run_id: UUID, owner: UUID, *, lock: bool = False) -> WorkflowRun:
        run = await self.repo.run(run_id, owner, lock=lock)
        definition = await self.session.get(WorkflowDefinition, run.workflow_definition_id)
        if definition is None or definition.key != "study_scheduler":
            raise UnauthorizedResourceAccess()
        return run

    async def create(self, owner: UUID) -> RunRead:
        definition = await self.session.scalar(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.key == "study_scheduler")
            .order_by(WorkflowDefinition.version.desc())
        )
        if definition is None:
            raise UnauthorizedResourceAccess()
        return await self.workflow.create(owner, RunInput(workflow_definition_id=definition.id))

    async def setup(self, run_id: UUID, owner: UUID, data: PlanSetupInput) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise PlanWorkflowInvalidState()
        if data.start.tzinfo is None or data.end.tzinfo is None or data.start >= data.end:
            raise SchedulingInputInvalid()
        payload: dict[str, Any] = {
            "stage": "setup",
            "window": {"start": data.start.isoformat(), "end": data.end.isoformat()},
            "calendar_id": data.calendar_id,
            "notion_database_id": data.notion_database_id,
            "notion_mapping": data.notion_mapping,
            "tasks": [task.model_dump(mode="json") for task in data.tasks],
            "task_issues": [],
            "busy_intervals": [],
            "sessions": [],
            "locked_sessions": [],
        }
        run.input_payload = payload
        record(self.session, owner, "PLAN_SETUP_SAVED", run.id)
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def import_tasks(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise PlanWorkflowInvalidState()
        payload = dict(run.input_payload or {})
        tasks = [AcademicTask.model_validate(item) for item in payload.get("tasks", [])]
        mapping_data = payload.get("notion_mapping")
        database_id = payload.get("notion_database_id")
        if not tasks and not (database_id and mapping_data):
            try:
                default = await self.notion.default(owner)
            except NotionNotConnected:
                default = None
            if default is not None:
                database_id, mapping = default
                mapping_data = mapping.model_dump(mode="json")
                payload["notion_database_id"] = database_id
                payload["notion_mapping"] = mapping_data
        imported_from_notion = False
        if database_id and mapping_data:
            imported_from_notion = True
            connection = await self.notion.connection(owner)
            client = await self.notion.client(connection)
            pages = await client.query_database(database_id)
            imported = NotionTaskMapper(
                NotionTaskPropertyMapping.model_validate(mapping_data)
            ).map_pages(pages)
            tasks = list(imported.tasks)
            payload["task_issues"] = [issue.model_dump(mode="json") for issue in imported.issues]
        payload["tasks"] = [task.model_dump(mode="json") for task in tasks]
        payload["stage"] = "tasks_imported"
        run.input_payload = payload
        record(
            self.session,
            owner,
            "NOTION_TASKS_IMPORTED",
            run.id,
            {"task_count": len(tasks), "issue_count": len(payload.get("task_issues", []))},
        )
        await self.session.commit()
        if imported_from_notion and not tasks:
            raise NotionTaskImportEmpty()
        return await self.detail(run_id, owner)

    async def generate(self, run_id: UUID, owner: UUID, data: PlanSetupInput) -> dict[str, Any]:
        await self.setup(run_id, owner, data)
        await self.import_tasks(run_id, owner)
        await self.load_availability(run_id, owner)
        return await self.solve(run_id, owner)

    async def load_availability(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.DRAFT:
            raise PlanWorkflowInvalidState()
        payload = dict(run.input_payload or {})
        start = datetime.fromisoformat(payload["window"]["start"])
        end = datetime.fromisoformat(payload["window"]["end"])
        calendar_id = await self.calendar_id(owner, payload.get("calendar_id"))
        busy: list[BusyInterval] = []
        if calendar_id:
            connection = await self.google.connection(owner)
            client = await self.google.client(connection)
            busy = await client.busy_intervals(calendar_id, start, end)
        payload["calendar_id"] = calendar_id
        payload["busy_intervals"] = [item.model_dump(mode="json") for item in busy]
        payload["stage"] = "availability_loaded"
        run.input_payload = payload
        record(
            self.session,
            owner,
            "CALENDAR_AVAILABILITY_LOADED",
            run.id,
            {"busy_interval_count": len(busy), "calendar_id": calendar_id},
        )
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def solve(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        # Regeneration (calling solve again after PLAN_READY) is only safe
        # before an approval has been requested: once AWAITING_APPROVAL, the
        # proposed action and approval already reflect the prior sessions,
        # and regenerating out from under them would approve stale data.
        if run.status not in {S.DRAFT, S.PLAN_READY}:
            raise PlanWorkflowInvalidState()
        payload = dict(run.input_payload or {})
        tasks = tuple(AcademicTask.model_validate(item) for item in payload.get("tasks", []))
        if not tasks:
            raise SchedulingInputInvalid()
        preference = self.scheduler.preference_from_user(await self.repo.preferences(owner))
        start = datetime.fromisoformat(payload["window"]["start"])
        end = datetime.fromisoformat(payload["window"]["end"])
        problem = SchedulingProblem(
            tasks=tasks,
            availability_windows=self.availability_windows(start, end, preference.timezone),
            busy_intervals=tuple(
                BusyInterval.model_validate(item) for item in payload.get("busy_intervals", [])
            ),
            preferences=preference,
            locked_sessions=tuple(
                StudySession.model_validate(item) for item in payload.get("locked_sessions", [])
            ),
            now=start,
        )
        record(self.session, owner, "SCHEDULING_STARTED", run.id, {"task_count": len(tasks)})
        result = self.scheduler.solve(problem)
        run.plan_payload = result.model_dump(mode="json")
        payload["sessions"] = [item.model_dump(mode="json") for item in result.sessions]
        payload["stage"] = "schedule_ready"
        run.input_payload = payload
        event = (
            "SCHEDULING_INFEASIBLE"
            if result.status == SchedulingStatus.INFEASIBLE
            else "SCHEDULING_COMPLETED"
        )
        record(
            self.session,
            owner,
            event,
            run.id,
            {
                "session_count": len(result.sessions),
                "unscheduled_minutes": result.metrics.unscheduled_minutes,
            },
        )
        if run.status == S.DRAFT:
            await self.workflow.apply_transition(run, S.ANALYZING, owner)
            await self.workflow.apply_transition(run, S.PLAN_READY, owner)
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def adjust_sessions(
        self, run_id: UUID, owner: UUID, sessions: tuple[StudySession, ...]
    ) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        # Once AWAITING_APPROVAL, the pending approval already froze a
        # payload built from the current sessions; edits after that point
        # would silently drift from what the consultant is reviewing.
        if run.status != S.PLAN_READY:
            raise PlanWorkflowInvalidState()
        payload = dict(run.input_payload or {})
        payload["sessions"] = [item.model_dump(mode="json") for item in sessions]
        payload["locked_sessions"] = [
            item.model_dump(mode="json") for item in sessions if item.locked
        ]
        run.input_payload = payload
        if run.plan_payload:
            result = SchedulingResult.model_validate(run.plan_payload)
            run.plan_payload = result.model_copy(update={"sessions": sessions}).model_dump(
                mode="json"
            )
        record(self.session, owner, "SESSION_MOVED", run.id, {"session_count": len(sessions)})
        await self.session.commit()
        return await self.detail(run_id, owner)

    async def request_approval(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner, lock=True)
        if run.status != S.PLAN_READY or run.plan_payload is None:
            raise PlanWorkflowInvalidState()
        result = SchedulingResult.model_validate(run.plan_payload)
        if not result.sessions or result.status == SchedulingStatus.INFEASIBLE:
            raise SchedulingInputInvalid()
        calendar_id = await self.calendar_id(owner, (run.input_payload or {}).get("calendar_id"))
        if not calendar_id:
            raise SchedulingInputInvalid()
        connection_id, calendar_summary = await self.google_connection_metadata(owner, calendar_id)
        events = tuple(
            CreateCalendarStudyBlockAction(
                task_id=session.task_id,
                title=f"Study: {self.task_title(run, session.task_id)}",
                start=session.start,
                end=session.end,
                description="Created by Relay after PLAN approval.",
                calendar_id=calendar_id,
                connection_id=connection_id,
                metadata={"workflow_run_id": str(run.id), "session_id": session.id},
            )
            for session in result.sessions
        )
        action_payload = CreateCalendarStudyPlanAction(
            connection_id=connection_id,
            calendar_id=calendar_id,
            calendar_summary=calendar_summary,
            events=events,
        ).model_dump(mode="json")
        action = ProposedAction(
            workflow_run_id=run.id,
            provider=ActionProvider.GOOGLE_CALENDAR,
            action_type=OPERATION,
            payload=action_payload,
            status=ActionStatus.PROPOSED,
        )
        self.session.add(action)
        await self.session.flush()
        record(
            self.session, owner, "PROPOSED_ACTION_CREATED", run.id, {"action_id": str(action.id)}
        )
        await self.workflow.request_approvals(run.id, owner)
        record(self.session, owner, "PLAN_APPROVAL_REQUESTED", run.id, {"event_count": len(events)})
        await self.session.commit()
        return await self.detail(run_id, owner)

    def availability_windows(
        self, start: datetime, end: datetime, timezone: str
    ) -> tuple[AvailabilityWindow, ...]:
        zone = ZoneInfo(timezone)
        windows: list[AvailabilityWindow] = []
        cursor = start.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        final = end.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        while cursor <= final:
            day_start = max(start, cursor)
            day_end = min(end, cursor + timedelta(days=1))
            if day_start < day_end:
                windows.append(AvailabilityWindow(start=day_start, end=day_end))
            cursor += timedelta(days=1)
        return tuple(windows)

    async def calendar_id(self, owner: UUID, selected: str | None) -> str | None:
        if selected:
            return selected
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.GOOGLE)
            if item.status == ConnectionStatus.CONNECTED
        ]
        if not connections:
            return None
        return connections[0].provider_metadata.get("default_calendar_id")

    async def google_connection_metadata(
        self, owner: UUID, calendar_id: str
    ) -> tuple[str | None, str | None]:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.GOOGLE)
            if item.status == ConnectionStatus.CONNECTED
        ]
        if not connections:
            return None, None
        connection = connections[0]
        return str(connection.id), connection.provider_metadata.get(
            "default_calendar_summary"
        ) or calendar_id

    def task_title(self, run: WorkflowRun, task_id: str) -> str:
        for item in (run.input_payload or {}).get("tasks", []):
            if item.get("id") == task_id:
                return str(item.get("title") or task_id)
        return task_id

    async def detail(self, run_id: UUID, owner: UUID) -> dict[str, Any]:
        run = await self.owned_run(run_id, owner)
        approvals = await self.repo.run_approvals(run_id)
        setup_payload = run.input_payload or None
        return {
            "run": RunRead.model_validate(run).model_dump(mode="json"),
            "setup": setup_payload,
            "result": run.plan_payload,
            "approval": ApprovalRead.model_validate(approvals[0]).model_dump(mode="json")
            if approvals
            else None,
        }
