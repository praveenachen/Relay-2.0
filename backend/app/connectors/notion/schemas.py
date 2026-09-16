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
        "callout",
        "divider",
        "quote",
    ]
    text: str = ""
    rich_text: list["NotionRichText"] = Field(default_factory=list)
    color: Literal[
        "default",
        "gray",
        "gray_background",
        "green",
        "green_background",
        "purple",
        "purple_background",
        "red",
        "red_background",
    ] = "default"
    icon_emoji: str | None = None
    children: list["NotionBlock"] = Field(default_factory=list)


class NotionRichText(StrictModel):
    text: str
    bold: bool = False
    italic: bool = False
    color: Literal["default", "gray", "green", "purple", "red"] = "default"
    href: str | None = None


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
    simulated: bool = False


class PublishNotionProjectAction(StrictModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    blocks: tuple[NotionBlock, ...]
    connection_id: str
    parent_destination_id: str
    parent_destination_title: str | None = None
    existing_page_id: str | None = None
    existing_page_url: str | None = None
    icon_emoji: str = "📌"
    legacy_blocks: tuple[NotionBlock, ...] = ()


class CreateNotionTaskDatabaseAction(StrictModel):
    title: str
    parent_page_id: str
    properties: dict[str, Any]
    rows: tuple[dict[str, Any], ...] = ()
    connection_id: str | None = None


class NotionTaskDatabaseResult(StrictModel):
    external_id: str
    external_url: str
    title: str
    task_count: int


class NotionConnector(Protocol):
    """Approval-gated writes only (runtime/factory.py + RuntimeClient). PLAN's
    Notion export is a direct, unapproved action -- see
    study_plan_export.py -- so create_task_database intentionally isn't part
    of this Protocol; it's a plain method on RealNotionConnector/
    MockNotionConnector, typed as a Union where it's used."""

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

    async def publish_project(
        self,
        action: PublishNotionProjectAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult: ...
