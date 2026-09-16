from uuid import NAMESPACE_URL, uuid5

from app.connectors.notion.errors import MockNotionFailure
from app.connectors.notion.mapper import NotionStudyPageMapper
from app.connectors.notion.schemas import (
    CreateNotionStudyPageAction,
    CreateNotionTaskAction,
    CreateNotionTaskDatabaseAction,
    ExternalArtifactResult,
    NotionTaskDatabaseResult,
    NotionTaskResult,
    PublishNotionProjectAction,
)


class MockNotionConnector:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        if self.fail:
            raise MockNotionFailure()
        identifier = "mock-" + uuid5(NAMESPACE_URL, idempotency_key).hex
        return ExternalArtifactResult(
            external_id=identifier,
            external_url=f"mock://notion/page/{identifier}",
            title=action.title,
            workspace_id=action.workspace_id,
            workspace_name=action.workspace_name,
            destination_id=action.parent_destination_id,
            destination_title=action.parent_destination_title,
            simulated=True,
            blocks=NotionStudyPageMapper().map(action.content.summary),
        )

    async def create_task(
        self,
        action: CreateNotionTaskAction,
        idempotency_key: str,
    ) -> NotionTaskResult:
        if self.fail:
            raise MockNotionFailure()
        identifier = "mock-" + uuid5(NAMESPACE_URL, idempotency_key).hex
        return NotionTaskResult(
            external_id=identifier,
            external_url=f"mock://notion/page/{identifier}",
            title=action.title,
            simulated=True,
        )

    async def publish_project(
        self,
        action: PublishNotionProjectAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        if self.fail:
            raise MockNotionFailure()
        identifier = action.existing_page_id or (
            "mock-" + uuid5(NAMESPACE_URL, f"project:{action.project_id}").hex
        )
        return ExternalArtifactResult(
            external_id=identifier,
            external_url=action.existing_page_url or f"mock://notion/page/{identifier}",
            title=action.title,
            destination_id=action.parent_destination_id,
            destination_title=action.parent_destination_title,
            simulated=True,
            blocks=list(action.blocks),
        )

    async def create_task_database(
        self,
        action: CreateNotionTaskDatabaseAction,
        idempotency_key: str,
    ) -> NotionTaskDatabaseResult:
        if self.fail:
            raise MockNotionFailure()
        identifier = "mock-" + uuid5(NAMESPACE_URL, idempotency_key).hex
        return NotionTaskDatabaseResult(
            external_id=identifier,
            external_url=f"mock://notion/database/{identifier}",
            title=action.title,
            task_count=len(action.rows),
        )
