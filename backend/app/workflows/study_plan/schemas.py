from datetime import datetime

from pydantic import Field

from app.scheduling.models import AcademicTask, StudySession
from app.workflows.lecture_notes.schemas import StrictModel


class PlanSetupInput(StrictModel):
    start: datetime
    end: datetime
    calendar_id: str | None = None
    tasks: tuple[AcademicTask, ...] = ()


class NotionExportInput(StrictModel):
    destination_page_id: str = Field(min_length=1)


class TaskReviewInput(StrictModel):
    tasks: tuple[AcademicTask, ...] = Field(min_length=1)


class SessionAdjustmentInput(StrictModel):
    sessions: tuple[StudySession, ...]


class LockSessionInput(StrictModel):
    session_id: str
    locked: bool = True
