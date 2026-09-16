from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.domain.enums import WorkflowStatus
from app.models.entities import ExternalArtifact, WorkflowRun
from app.projects.schemas import ProjectPlanInput, ScheduledBlockRead
from app.repositories.relay import RelayRepository
from app.scheduling.project_adapter import project_task_to_scheduler_input
from app.workflows.study_plan.errors import SchedulingInputInvalid
from app.workflows.study_plan.schemas import PlanSetupInput
from app.workflows.study_plan.service import StudyPlanWorkflowService


class ProjectPlanningService:
    def __init__(self, repo: RelayRepository, planner: StudyPlanWorkflowService):
        self.repo = repo
        self.planner = planner

    async def generate(
        self, project_id: UUID, owner: UUID, data: ProjectPlanInput
    ) -> dict[str, object]:
        project = await self.repo.project(project_id, owner)
        selected = set(data.task_ids)
        tasks = [task for task in await self.repo.tasks(project_id, owner) if task.id in selected]
        if len(tasks) != len(selected):
            raise SchedulingInputInvalid()
        adapted = tuple(
            item
            for task in tasks
            if (item := project_task_to_scheduler_input(task, project)) is not None
        )
        if len(adapted) != len(tasks):
            raise SchedulingInputInvalid()
        created = await self.planner.create(owner)
        run = await self.repo.run(created.id, owner, lock=True)
        run.project_workspace_id = project.id
        await self.repo.session.commit()
        return await self.planner.generate(
            run.id,
            owner,
            PlanSetupInput(
                start=data.start,
                end=data.end,
                calendar_id=data.calendar_id,
                tasks=adapted,
            ),
        )

    async def scheduled_blocks(self, owner: UUID) -> list[ScheduledBlockRead]:
        runs = (
            await self.repo.session.scalars(
                select(WorkflowRun)
                .where(
                    WorkflowRun.user_id == owner,
                    WorkflowRun.project_workspace_id.is_not(None),
                    WorkflowRun.status.in_(
                        [WorkflowStatus.COMPLETED, WorkflowStatus.PARTIALLY_COMPLETED]
                    ),
                )
                .order_by(WorkflowRun.created_at.desc())
            )
        ).all()
        blocks: list[ScheduledBlockRead] = []
        seen: set[tuple[UUID, datetime, datetime]] = set()
        for run in runs:
            if run.project_workspace_id is None:
                continue
            project = await self.repo.project(run.project_workspace_id, owner)
            tasks = {str(task.id): task for task in await self.repo.tasks(project.id, owner)}
            artifacts = (
                await self.repo.session.scalars(
                    select(ExternalArtifact).where(
                        ExternalArtifact.workflow_run_id == run.id,
                        ExternalArtifact.artifact_type == "calendar_study_block",
                    )
                )
            ).all()
            exported_indexes = {
                int(artifact.idempotency_key.rsplit(":", 1)[-1])
                for artifact in artifacts
                if artifact.idempotency_key.rsplit(":", 1)[-1].isdigit()
            }
            for index, raw in enumerate((run.input_payload or {}).get("sessions", [])):
                if index not in exported_indexes:
                    continue
                task = tasks.get(str(raw.get("task_id")))
                if task is None:
                    continue
                start = datetime.fromisoformat(str(raw["start"]))
                end = datetime.fromisoformat(str(raw["end"]))
                key = (task.id, start, end)
                if key in seen:
                    continue
                seen.add(key)
                blocks.append(
                    ScheduledBlockRead(
                        run_id=run.id,
                        project_id=project.id,
                        project_name=project.name,
                        task_id=task.id,
                        task_title=task.title,
                        start=start,
                        end=end,
                    )
                )
        return sorted(blocks, key=lambda block: block.start)
