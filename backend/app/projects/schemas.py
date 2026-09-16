from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.workflows.lecture_notes.schemas import StrictModel


class ProjectPlanInput(StrictModel):
    task_ids: tuple[UUID, ...] = Field(min_length=1)
    start: datetime
    end: datetime
    calendar_id: str | None = None


class GitHubIssuePreviewInput(StrictModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=10_000)


class GitHubIssuePreview(StrictModel):
    run_id: UUID
    approval_id: UUID
    task_id: UUID
    title: str
    description: str
    repository: str


class ScheduledBlockRead(StrictModel):
    run_id: UUID
    project_id: UUID
    project_name: str
    task_id: UUID
    task_title: str
    start: datetime
    end: datetime


class NotionProjectStatus(StrictModel):
    connected: bool
    destination_configured: bool
    destination_title: str | None = None
    page_id: str | None = None
    page_url: str | None = None
    last_published_at: datetime | None = None


class NotionProjectPreview(StrictModel):
    run_id: UUID
    approval_id: UUID
    title: str
    is_update: bool
    progress: int
    task_count: int
    source_count: int
    deadline: datetime | None = None
    destination_title: str | None = None
