from datetime import time

from sqlalchemy import delete, select

from app.domain.enums import Provider
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    ExternalArtifact,
    GoogleCalendarRecord,
    NotionDestinationRecord,
    NotionTaskDatabaseRecord,
    OAuthState,
    ProjectMember,
    ProjectWorkspace,
    ProposedAction,
    SourceDocument,
    User,
    WorkflowRun,
)
from app.repositories.relay import RelayRepository
from app.services.audit import record


class ProfileHistoryService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository
        self.session = repository.session

    async def reset(self, user: User) -> None:
        owner = user.id
        run_ids = list(
            await self.session.scalars(select(WorkflowRun.id).where(WorkflowRun.user_id == owner))
        )
        project_ids = list(
            await self.session.scalars(
                select(ProjectWorkspace.id).where(ProjectWorkspace.user_id == owner)
            )
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
            await self.session.execute(delete(WorkflowRun).where(WorkflowRun.id.in_(run_ids)))

        if project_ids:
            await self.session.execute(
                delete(ProjectMember).where(ProjectMember.project_workspace_id.in_(project_ids))
            )
            await self.session.execute(
                delete(ProjectWorkspace).where(ProjectWorkspace.id.in_(project_ids))
            )

        await self.session.execute(
            delete(NotionDestinationRecord).where(NotionDestinationRecord.user_id == owner)
        )
        await self.session.execute(
            delete(NotionTaskDatabaseRecord).where(NotionTaskDatabaseRecord.user_id == owner)
        )
        await self.session.execute(
            delete(GoogleCalendarRecord).where(GoogleCalendarRecord.user_id == owner)
        )
        await self.session.execute(delete(OAuthState).where(OAuthState.user_id == owner))
        await self.session.execute(delete(AuditEvent).where(AuditEvent.user_id == owner))

        preference = await self.repo.preferences(owner)
        preference.timezone = "UTC"
        preference.earliest_study_time = time(8)
        preference.latest_study_time = time(22)
        preference.preferred_session_minutes = 50
        preference.maximum_session_minutes = 90
        preference.minimum_break_minutes = 10
        user.onboarding_completed = False

        connections = await self.repo.connections(owner, lock=True)
        for connection in connections:
            metadata = dict(connection.provider_metadata or {})
            if connection.provider == Provider.NOTION:
                metadata.pop("default_destination_id", None)
                metadata.pop("default_destination_title", None)
            if connection.provider == Provider.GOOGLE:
                metadata.pop("default_calendar_id", None)
                metadata.pop("default_calendar_summary", None)
            connection.provider_metadata = metadata

        record(self.session, owner, "PROFILE_HISTORY_RESET")
        await self.session.commit()
