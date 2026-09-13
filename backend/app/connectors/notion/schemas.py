from typing import Any, Literal, Protocol

from pydantic import ConfigDict, Field

from app.workflows.lecture_notes.schemas import LectureSummary, StrictModel


class NotionStudyPageContent(StrictModel):
    summary: LectureSummary


class CreateNotionStudyPageAction(StrictModel):
    title: str = Field(min_length=1, max_length=255)
    connection_id: str | None = None
    parent_destination_id: str | None = None
    parent_destination_title: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    content: NotionStudyPageContent


class NotionBlock(StrictModel):
    kind: Literal[
        "heading_1",
        "heading_2",
        "paragraph",
        "bulleted_list_item",
        "numbered_list_item",
        "equation",
        "toggle",
    ]
    text: str
    children: list["NotionBlock"] = Field(default_factory=list)


class ExternalArtifactResult(StrictModel):
    external_id: str
    external_url: str
    title: str
    workspace_id: str | None = None
    workspace_name: str | None = None
    destination_id: str | None = None
    destination_title: str | None = None
    simulated: bool = False
    blocks: list[NotionBlock] = Field(default_factory=list)


class NotionDestination(StrictModel):
    id: str
    title: str
    icon_url: str | None = None
    object_type: str = "page"


class NotionOAuthToken(StrictModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str | None = None
    bot_id: str
    workspace_id: str
    workspace_name: str | None = None
    workspace_icon: str | None = None
    owner: dict[str, Any] = Field(default_factory=dict)
    duplicated_template_id: str | None = None


class CreateNotionTaskAction(StrictModel):
    task_id: str
    database_id: str
    title: str
    properties: dict[str, Any]
    body_blocks: tuple[NotionBlock, ...] = ()
    connection_id: str | None = None


class NotionTaskResult(StrictModel):
    external_id: str
    external_url: str
    title: str


class NotionConnector(Protocol):
    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult: ...

    async def create_task(
        self,
        action: CreateNotionTaskAction,
        idempotency_key: str,
    ) -> NotionTaskResult: ...


class NotionTaskDatabaseProperty(StrictModel):
    name: str
    type: str


class NotionTaskDatabase(StrictModel):
    id: str
    title: str
    properties: list[NotionTaskDatabaseProperty] = Field(default_factory=list)
