from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal[
    "ASSIGNMENT_BRIEF",
    "COURSE_OUTLINE",
    "STUDY_GOAL",
    "MEETING_TRANSCRIPT",
    "DOCUMENT_BRIEF",
    "PERSONAL_GOAL",
    "NOTES_CHECKLIST",
]
Priority = Literal["LOW", "MEDIUM", "HIGH"]
ConfirmationField = Literal["due_date", "owner", "details"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskProposal(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    due_date: datetime | None = None
    estimate_minutes: int | None = Field(default=None, ge=5, le=1440)
    priority: Priority | None = None
    owner: str | None = Field(default=None, max_length=200)
    source_reference: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=1000)
    needs_confirmation: list[ConfirmationField] = Field(default_factory=list)


class TaskProposalBatch(StrictModel):
    proposals: list[TaskProposal] = Field(min_length=1, max_length=12)


class TaskProposalEdit(TaskProposal):
    source_id: UUID
    project_id: UUID
    possible_duplicate: bool = False
    duplicate_of_title: str | None = Field(default=None, max_length=300)


class SourceRead(StrictModel):
    id: UUID
    project_workspace_id: UUID
    source_type: SourceType
    title: str
    original_filename: str | None
    status: Literal["PROCESSING", "READY", "FAILED"]
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TaskProposalRead(StrictModel):
    approval_id: UUID
    run_id: UUID
    action_id: UUID
    status: Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED"]
    project_id: UUID
    project_name: str
    project_space: Literal["SCHOOL", "WORK", "PERSONAL"]
    source_id: UUID
    source_title: str
    source_type: SourceType
    proposal: TaskProposalEdit
    requested_at: datetime


class TaskRead(StrictModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    due_date: datetime | None
    estimate_minutes: int | None
    priority: Priority | None
    status: Literal["TODO", "IN_PROGRESS", "DONE"]
    source_id: UUID | None
    source_title: str | None = None
    source_type: SourceType | None = None
    source_reference: str | None
    created_at: datetime


class TaskExecutionResult(StrictModel):
    task_id: UUID
    duplicate: bool = False


class SourceCaptureInput(StrictModel):
    source_type: SourceType
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    original_filename: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def clean_content(self) -> "SourceCaptureInput":
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("Source content is required")
        return self
