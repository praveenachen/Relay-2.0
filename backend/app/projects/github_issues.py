from uuid import UUID

from sqlalchemy import select

from app.connectors.github.errors import GitHubNotConnected, GitHubRepositoryNotFound
from app.connectors.github.schemas import CreateGitHubIssueAction
from app.domain.enums import ActionProvider, ActionStatus, ConnectionStatus, Provider, RiskLevel
from app.domain.enums import WorkflowStatus as S
from app.models.entities import ApprovalRequest, ProposedAction, WorkflowDefinition, WorkflowRun
from app.projects.schemas import GitHubIssuePreview, GitHubIssuePreviewInput
from app.repositories.relay import RelayRepository
from app.runtime.client import RuntimeClient
from app.schemas.domain import RunInput, RunRead
from app.services.approvals import ApprovalService
from app.services.workflows import WorkflowService
from app.workflows.project_meeting.actions import CREATE_GITHUB_ISSUE_OPERATION
from app.workflows.project_meeting.execution import CollaborateExecutionService


class ProjectGitHubIssueService:
    def __init__(self, repo: RelayRepository, runtime: RuntimeClient):
        self.repo = repo
        self.session = repo.session
        self.runtime = runtime

    async def preview(
        self,
        project_id: UUID,
        task_id: UUID,
        owner: UUID,
        data: GitHubIssuePreviewInput,
    ) -> GitHubIssuePreview:
        project = await self.repo.project(project_id, owner)
        task = await self.repo.task(project_id, task_id, owner)
        if not project.github_repository_owner or not project.github_repository_name:
            raise GitHubRepositoryNotFound()
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.GITHUB)
            if item.status == ConnectionStatus.CONNECTED
        ]
        if not connections:
            raise GitHubNotConnected()

        existing_actions = (
            await self.session.scalars(
                select(ProposedAction)
                .join(
                    WorkflowRun,
                    WorkflowRun.id == ProposedAction.workflow_run_id,
                )
                .where(
                    WorkflowRun.user_id == owner,
                    WorkflowRun.project_workspace_id == project.id,
                    ProposedAction.action_type == CREATE_GITHUB_ISSUE_OPERATION,
                    ProposedAction.status != ActionStatus.FAILED,
                )
                .order_by(ProposedAction.created_at.desc())
            )
        ).all()
        for existing in existing_actions:
            if existing.payload.get("task_id") != str(task.id):
                continue
            approval = await self.session.scalar(
                select(ApprovalRequest).where(ApprovalRequest.proposed_action_id == existing.id)
            )
            if approval is not None:
                return GitHubIssuePreview(
                    run_id=existing.workflow_run_id,
                    approval_id=approval.id,
                    task_id=task.id,
                    title=str(existing.payload.get("title") or task.title),
                    description=str(existing.payload.get("body") or ""),
                    repository=(
                        f"{project.github_repository_owner}/{project.github_repository_name}"
                    ),
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
            raise GitHubRepositoryNotFound()
        workflow = WorkflowService(self.repo)
        created = await workflow.create(
            owner,
            RunInput(
                workflow_definition_id=definition.id,
                input_payload={"kind": "project_task_github_issue", "task_id": str(task.id)},
            ),
        )
        run = await self.repo.run(created.id, owner, lock=True)
        run.project_workspace_id = project.id
        await workflow.apply_transition(run, S.ANALYZING, owner)
        await workflow.apply_transition(run, S.PLAN_READY, owner)
        payload = CreateGitHubIssueAction(
            task_id=str(task.id),
            repository_owner=project.github_repository_owner,
            repository_name=project.github_repository_name,
            title=data.title,
            body=data.description,
            connection_id=str(connections[0].id),
            metadata={"project_id": str(project.id)},
        ).model_dump(mode="json")
        action = ProposedAction(
            workflow_run_id=run.id,
            provider=ActionProvider.GITHUB,
            action_type=CREATE_GITHUB_ISSUE_OPERATION,
            payload=payload,
            risk_level=RiskLevel.MEDIUM,
            status=ActionStatus.PROPOSED,
        )
        self.session.add(action)
        await self.session.flush()
        await workflow.request_approvals(run.id, owner)
        approval = (await self.repo.run_approvals(run.id))[0]
        return GitHubIssuePreview(
            run_id=run.id,
            approval_id=approval.id,
            task_id=task.id,
            title=data.title,
            description=data.description,
            repository=f"{project.github_repository_owner}/{project.github_repository_name}",
        )

    async def confirm(
        self, run_id: UUID, approval_id: UUID, owner: UUID, project_id: UUID, task_id: UUID
    ) -> RunRead:
        run = await self.repo.run(run_id, owner)
        approval = await self.repo.approval(approval_id, owner)
        if approval.workflow_run_id != run.id or run.project_workspace_id != project_id:
            raise GitHubRepositoryNotFound()
        action = await self.session.get(ProposedAction, approval.proposed_action_id)
        if action is None or action.payload.get("task_id") != str(task_id):
            raise GitHubRepositoryNotFound()
        if approval.status.value == "PENDING":
            await ApprovalService(self.repo).resolve(
                approval.id, owner, approval.original_payload, approve=True
            )
        return await CollaborateExecutionService(self.repo, self.runtime).execute(run.id, owner)
