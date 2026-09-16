from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.connectors.notion.errors import NotionDestinationNotFound, NotionNotConnected
from app.connectors.notion.schemas import (
    NotionBlock,
    NotionRichText,
    PublishNotionProjectAction,
)
from app.domain.enums import ActionProvider, ActionStatus, ConnectionStatus, Provider, RiskLevel
from app.domain.enums import WorkflowStatus as S
from app.models.entities import (
    ApprovalRequest,
    ConnectedAccount,
    ExternalArtifact,
    ProjectTask,
    ProposedAction,
    WorkflowDefinition,
    WorkflowRun,
)
from app.projects.schemas import NotionProjectPreview, NotionProjectStatus
from app.repositories.relay import RelayRepository
from app.runtime.client import RuntimeClient
from app.schemas.domain import RunInput, RunRead
from app.services.approvals import ApprovalService
from app.services.workflows import WorkflowService
from app.workflows.project_meeting.execution import CollaborateExecutionService

OPERATION = "publish_notion_project"
ARTIFACT_TYPES = ("notion_project_page", "mock_notion_project_page")


def _human_date(value: datetime) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _human_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _duration(minutes: int | None) -> str | None:
    if not minutes:
        return None
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


def _task_block(task: ProjectTask) -> NotionBlock:
    due_date = task.due_date
    estimate = _duration(task.estimate_minutes)
    priority = task.priority
    metadata = []
    if due_date:
        metadata.append(f"Due {_human_date(due_date)}")
    if estimate:
        metadata.append(estimate)
    if priority:
        metadata.append(f"{str(priority).title()} priority")
    rich_text = [NotionRichText(text=task.title, bold=True)]
    if metadata:
        rich_text.append(NotionRichText(text=f"\n{' · '.join(metadata)}", color="gray"))
    return NotionBlock(kind="bulleted_list_item", rich_text=rich_text)


class ProjectNotionPublishService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient | None = None):
        self.repo = repo
        self.session = repo.session
        self.runtime = runtime

    async def _connection(self, owner: UUID) -> ConnectedAccount:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.NOTION)
            if item.status == ConnectionStatus.CONNECTED and item.access_token_encrypted
        ]
        if not connections:
            raise NotionNotConnected()
        return connections[0]

    async def _artifact(self, project_id: UUID, owner: UUID) -> ExternalArtifact | None:
        artifact = await self.session.scalar(
            select(ExternalArtifact)
            .join(WorkflowRun, WorkflowRun.id == ExternalArtifact.workflow_run_id)
            .where(
                WorkflowRun.user_id == owner,
                WorkflowRun.project_workspace_id == project_id,
                ExternalArtifact.provider == ActionProvider.NOTION,
                ExternalArtifact.artifact_type.in_(ARTIFACT_TYPES),
            )
            .order_by(ExternalArtifact.created_at.desc())
        )
        return artifact

    async def status(self, project_id: UUID, owner: UUID) -> NotionProjectStatus:
        await self.repo.project(project_id, owner)
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.NOTION)
            if item.status == ConnectionStatus.CONNECTED
        ]
        connection = connections[0] if connections else None
        artifact = await self._artifact(project_id, owner)
        destination = (connection.provider_metadata or {}) if connection else {}
        return NotionProjectStatus(
            connected=connection is not None,
            destination_configured=bool(destination.get("default_destination_id")),
            destination_title=destination.get("default_destination_title"),
            page_id=artifact.external_id if artifact else None,
            page_url=artifact.external_url if artifact else None,
            last_published_at=artifact.created_at if artifact else None,
        )

    async def preview(self, project_id: UUID, owner: UUID) -> NotionProjectPreview:
        project = await self.repo.project(project_id, owner)
        connection = await self._connection(owner)
        metadata = connection.provider_metadata or {}
        destination_id = metadata.get("default_destination_id")
        if not isinstance(destination_id, str):
            raise NotionDestinationNotFound()
        artifact = await self._artifact(project_id, owner)
        tasks = list(await self.repo.tasks(project.id, owner))
        sources = list(await self.repo.sources(project.id, owner))
        done = sum(task.status == "DONE" for task in tasks)
        progress = round(done / len(tasks) * 100) if tasks else 0
        pending_action = await self.session.scalar(
            select(ProposedAction)
            .join(WorkflowRun, WorkflowRun.id == ProposedAction.workflow_run_id)
            .where(
                WorkflowRun.user_id == owner,
                WorkflowRun.project_workspace_id == project.id,
                ProposedAction.action_type == OPERATION,
                ProposedAction.status.in_(
                    (
                        ActionStatus.PROPOSED,
                        ActionStatus.EDITED,
                        ActionStatus.APPROVED,
                        ActionStatus.QUEUED,
                        ActionStatus.EXECUTING,
                    )
                ),
            )
            .order_by(ProposedAction.created_at.desc())
        )
        if pending_action is not None:
            pending_approval = await self.session.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.proposed_action_id == pending_action.id
                )
            )
            if pending_approval is not None:
                return NotionProjectPreview(
                    run_id=pending_action.workflow_run_id,
                    approval_id=pending_approval.id,
                    title=project.name,
                    is_update=bool(pending_action.payload.get("existing_page_id")),
                    progress=progress,
                    task_count=len(tasks),
                    source_count=len(sources),
                    deadline=project.deadline,
                    destination_title=metadata.get("default_destination_title"),
                )
        preference = await self.repo.preferences(owner)
        try:
            timezone = ZoneInfo(preference.timezone)
        except (KeyError, ValueError):
            timezone = ZoneInfo("UTC")
        plan_run = await self.session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.user_id == owner,
                WorkflowRun.project_workspace_id == project.id,
                WorkflowRun.plan_payload.is_not(None),
            )
            .order_by(WorkflowRun.updated_at.desc())
        )
        plan_sessions = list((plan_run.plan_payload or {}).get("sessions", [])) if plan_run else []
        task_titles = {str(task.id): task.title for task in tasks}
        open_tasks = sorted(
            (task for task in tasks if task.status != "DONE"),
            key=lambda item: (
                item.due_date.isoformat() if item.due_date else "9999-12-31",
                item.title,
            ),
        )
        completed_tasks = sorted(
            (task for task in tasks if task.status == "DONE"),
            key=lambda item: item.title,
        )
        children: list[NotionBlock] = []
        if project.description:
            children.extend(
                [
                    NotionBlock(kind="heading_2", text="Goal"),
                    NotionBlock(
                        kind="quote",
                        text=project.description,
                        color="gray_background",
                    ),
                ]
            )
        children.append(NotionBlock(kind="divider"))
        children.append(NotionBlock(kind="heading_2", text="Open tasks"))
        if open_tasks:
            children.extend(_task_block(task) for task in open_tasks[:35])
        else:
            children.append(
                NotionBlock(
                    kind="paragraph",
                    rich_text=[
                        NotionRichText(
                            text="Everything is complete.",
                            italic=True,
                            color="green",
                        )
                    ],
                )
            )
        if completed_tasks:
            children.append(
                NotionBlock(
                    kind="toggle",
                    text=f"Completed ({len(completed_tasks)})",
                    color="green",
                    children=[_task_block(task) for task in completed_tasks[:15]],
                )
            )
        if plan_sessions:
            children.append(NotionBlock(kind="heading_2", text="Scheduled this week"))
            previous_day = None
            for raw in sorted(plan_sessions, key=lambda item: str(item.get("start")))[:14]:
                try:
                    start = datetime.fromisoformat(str(raw["start"])).astimezone(timezone)
                    end = datetime.fromisoformat(str(raw["end"])).astimezone(timezone)
                except (KeyError, TypeError, ValueError):
                    continue
                day = start.date()
                if day != previous_day:
                    children.append(
                        NotionBlock(
                            kind="paragraph",
                            rich_text=[NotionRichText(text=_human_date(start), bold=True)],
                        )
                    )
                    previous_day = day
                title = task_titles.get(str(raw.get("task_id")), "Project task")
                children.append(
                    NotionBlock(
                        kind="bulleted_list_item",
                        rich_text=[
                            NotionRichText(
                                text=f"{_human_time(start)}–{_human_time(end)}",
                                bold=True,
                                color="purple",
                            ),
                            NotionRichText(text=f"  {title}"),
                        ],
                    )
                )
        if sources:
            children.append(
                NotionBlock(
                    kind="toggle",
                    text=f"Sources ({len(sources)})",
                    children=[
                        NotionBlock(
                            kind="bulleted_list_item",
                            rich_text=[
                                NotionRichText(text=source.title, bold=True),
                                NotionRichText(
                                    text=(" · " + source.source_type.replace("_", " ").title()),
                                    color="gray",
                                ),
                            ],
                        )
                        for source in sources[:8]
                    ],
                )
            )
        snapshot_times = [
            project.updated_at,
            *(task.updated_at for task in tasks),
            *(source.updated_at for source in sources),
        ]
        if plan_run is not None:
            snapshot_times.append(plan_run.updated_at)
        snapshot_at = max(snapshot_times)
        local_snapshot_at = snapshot_at.replace(tzinfo=snapshot_at.tzinfo or UTC).astimezone(
            timezone
        )
        children.extend(
            [
                NotionBlock(kind="divider"),
                NotionBlock(
                    kind="paragraph",
                    rich_text=[
                        NotionRichText(
                            text=(
                                "Published from Relay · Updated "
                                f"{_human_date(local_snapshot_at)} at "
                                f"{_human_time(local_snapshot_at)} · "
                                "Manage tasks and planning in Relay."
                            ),
                            italic=True,
                            color="gray",
                        )
                    ],
                ),
            ]
        )
        summary = [
            "Relay snapshot",
            f"{progress}% complete",
            f"{done} of {len(tasks)} tasks",
        ]
        if project.deadline:
            summary.append(f"Due {_human_date(project.deadline)}")
        icon = {"SCHOOL": "🎓", "WORK": "💼", "PERSONAL": "🌱"}.get(project.space, "📌")
        blocks = [
            NotionBlock(
                kind="callout",
                text=" · ".join(summary),
                icon_emoji=icon,
                color="purple_background",
                children=children[:99],
            )
        ]
        legacy_blocks: tuple[NotionBlock, ...] = ()
        if artifact is not None:
            previous_action = await self.session.get(ProposedAction, artifact.proposed_action_id)
            if previous_action is not None:
                legacy_blocks = tuple(
                    NotionBlock.model_validate(item)
                    for item in previous_action.payload.get("blocks", [])
                    if isinstance(item, dict)
                )
        action_payload = PublishNotionProjectAction(
            project_id=str(project.id),
            title=project.name,
            blocks=tuple(blocks),
            connection_id=str(connection.id),
            parent_destination_id=destination_id,
            parent_destination_title=metadata.get("default_destination_title"),
            existing_page_id=artifact.external_id if artifact else None,
            existing_page_url=artifact.external_url if artifact else None,
            icon_emoji=icon,
            legacy_blocks=legacy_blocks,
        )

        definition = await self.session.scalar(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.key == "project_meeting",
                WorkflowDefinition.enabled.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
        )
        if definition is None:
            raise NotionDestinationNotFound()
        workflow = WorkflowService(self.repo)
        created = await workflow.create(
            owner,
            RunInput(
                workflow_definition_id=definition.id,
                input_payload={"kind": OPERATION, "project_id": str(project.id)},
            ),
        )
        run = await self.repo.run(created.id, owner, lock=True)
        run.project_workspace_id = project.id
        await workflow.apply_transition(run, S.ANALYZING, owner)
        await workflow.apply_transition(run, S.PLAN_READY, owner)
        action = ProposedAction(
            workflow_run_id=run.id,
            provider=ActionProvider.NOTION,
            action_type=OPERATION,
            payload=action_payload.model_dump(mode="json"),
            risk_level=RiskLevel.MEDIUM,
            status=ActionStatus.PROPOSED,
        )
        self.session.add(action)
        await self.session.flush()
        await workflow.request_approvals(run.id, owner)
        approval = (await self.repo.run_approvals(run.id))[0]
        return NotionProjectPreview(
            run_id=run.id,
            approval_id=approval.id,
            title=project.name,
            is_update=artifact is not None,
            progress=progress,
            task_count=len(tasks),
            source_count=len(sources),
            deadline=project.deadline,
            destination_title=metadata.get("default_destination_title"),
        )

    async def confirm(self, run_id: UUID, approval_id: UUID, owner: UUID) -> RunRead:
        if self.runtime is None:
            raise NotionNotConnected()
        run = await self.repo.run(run_id, owner)
        approval = await self.repo.approval(approval_id, owner)
        if approval.workflow_run_id != run.id:
            raise NotionDestinationNotFound()
        if approval.status.value == "PENDING":
            await ApprovalService(self.repo).resolve(
                approval.id, owner, approval.original_payload, approve=True
            )
        return await CollaborateExecutionService(self.repo, self.runtime).execute(run.id, owner)
