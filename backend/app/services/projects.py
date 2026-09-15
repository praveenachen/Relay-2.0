from uuid import UUID

from sqlalchemy import ColumnElement, delete, or_, select

from app.domain.errors import ProjectNotFound
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ExternalArtifact,
    LocalExecution,
    ProjectMember,
    ProjectSource,
    ProjectTask,
    ProjectWorkspace,
    ProposedAction,
    SourceDocument,
    WorkflowRun,
)
from app.repositories.relay import RelayRepository
from app.schemas.domain import ProjectInput, ProjectMemberInput, ProjectMemberRead, ProjectRead
from app.services.audit import record


class ProjectService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository
        self.session = repository.session

    async def list_projects(self, owner: UUID) -> list[ProjectRead]:
        return [ProjectRead.model_validate(item) for item in await self.repo.projects(owner)]

    async def get(self, owner: UUID, project_id: UUID) -> ProjectRead:
        return ProjectRead.model_validate(await self.repo.project(project_id, owner))

    async def create(self, owner: UUID, data: ProjectInput) -> ProjectRead:
        project = ProjectWorkspace(user_id=owner, **data.model_dump())
        self.session.add(project)
        await self.session.flush()
        record(self.session, owner, "PROJECT_CREATED", metadata={"project_id": str(project.id)})
        await self.session.commit()
        return ProjectRead.model_validate(project)

    async def update(self, owner: UUID, project_id: UUID, data: ProjectInput) -> ProjectRead:
        project = await self.repo.project(project_id, owner, lock=True)
        for key, value in data.model_dump().items():
            setattr(project, key, value)
        record(self.session, owner, "PROJECT_UPDATED", metadata={"project_id": str(project.id)})
        await self.session.commit()
        return ProjectRead.model_validate(project)

    async def delete(self, owner: UUID, project_id: UUID) -> None:
        project = await self.repo.project(project_id, owner, lock=True)
        run_ids = list(
            await self.session.scalars(
                select(WorkflowRun.id).where(WorkflowRun.project_workspace_id == project.id)
            )
        )
        action_ids = (
            list(
                await self.session.scalars(
                    select(ProposedAction.id).where(ProposedAction.workflow_run_id.in_(run_ids))
                )
            )
            if run_ids
            else []
        )
        # Tasks retain both proposal and source provenance, so they must be
        # removed before either side of that relationship is cleared.
        await self.session.execute(
            delete(ProjectTask).where(ProjectTask.project_workspace_id == project.id)
        )
        if run_ids:
            await self.session.execute(
                delete(ApprovalRequest).where(ApprovalRequest.workflow_run_id.in_(run_ids))
            )
            await self.session.execute(
                delete(ExternalArtifact).where(ExternalArtifact.workflow_run_id.in_(run_ids))
            )
            await self.session.execute(
                delete(ProposedAction).where(ProposedAction.workflow_run_id.in_(run_ids))
            )
            await self.session.execute(
                delete(SourceDocument).where(SourceDocument.workflow_run_id.in_(run_ids))
            )
            await self.session.execute(
                delete(AuditEvent).where(AuditEvent.workflow_run_id.in_(run_ids))
            )
            execution_keys: list[ColumnElement[bool]] = [
                LocalExecution.idempotency_key.like(f"%:{run_id}:%") for run_id in run_ids
            ]
            execution_keys.extend(
                LocalExecution.idempotency_key == f"plan:{run_id}" for run_id in run_ids
            )
            execution_keys.extend(
                LocalExecution.idempotency_key == f"source-task:{action_id}"
                for action_id in action_ids
            )
            if execution_keys:
                await self.session.execute(delete(LocalExecution).where(or_(*execution_keys)))
            await self.session.execute(delete(WorkflowRun).where(WorkflowRun.id.in_(run_ids)))
        await self.session.execute(
            delete(ProjectSource).where(ProjectSource.project_workspace_id == project.id)
        )
        await self.session.execute(
            delete(ProjectMember).where(ProjectMember.project_workspace_id == project.id)
        )
        await self.session.delete(project)
        record(self.session, owner, "PROJECT_DELETED", metadata={"project_id": str(project_id)})
        await self.session.commit()

    async def members(self, owner: UUID, project_id: UUID) -> list[ProjectMemberRead]:
        await self.repo.project(project_id, owner)
        return [
            ProjectMemberRead.model_validate(item) for item in await self.repo.members(project_id)
        ]

    async def add_member(
        self, owner: UUID, project_id: UUID, data: ProjectMemberInput
    ) -> ProjectMemberRead:
        await self.repo.project(project_id, owner)
        member = ProjectMember(project_workspace_id=project_id, **data.model_dump())
        self.session.add(member)
        await self.session.flush()
        record(
            self.session,
            owner,
            "PROJECT_MEMBER_ADDED",
            metadata={"project_id": str(project_id), "member_id": str(member.id)},
        )
        await self.session.commit()
        return ProjectMemberRead.model_validate(member)

    async def update_member(
        self, owner: UUID, project_id: UUID, member_id: UUID, data: ProjectMemberInput
    ) -> ProjectMemberRead:
        await self.repo.project(project_id, owner)
        member = await self._owned_member(project_id, member_id)
        for key, value in data.model_dump().items():
            setattr(member, key, value)
        record(
            self.session,
            owner,
            "PROJECT_MEMBER_UPDATED",
            metadata={"project_id": str(project_id), "member_id": str(member.id)},
        )
        await self.session.commit()
        return ProjectMemberRead.model_validate(member)

    async def remove_member(self, owner: UUID, project_id: UUID, member_id: UUID) -> None:
        await self.repo.project(project_id, owner)
        member = await self._owned_member(project_id, member_id)
        await self.session.delete(member)
        record(
            self.session,
            owner,
            "PROJECT_MEMBER_REMOVED",
            metadata={"project_id": str(project_id), "member_id": str(member_id)},
        )
        await self.session.commit()

    async def _owned_member(self, project_id: UUID, member_id: UUID) -> ProjectMember:
        member = await self.session.get(ProjectMember, member_id)
        if member is None or member.project_workspace_id != project_id:
            raise ProjectNotFound()
        return member
