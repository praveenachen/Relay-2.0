from uuid import NAMESPACE_URL, uuid5

from app.connectors.notion.errors import MockNotionFailure
from app.connectors.notion.mapper import NotionStudyPageMapper
from app.connectors.notion.schemas import CreateNotionStudyPageAction, ExternalArtifactResult


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
