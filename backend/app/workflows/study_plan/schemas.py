from datetime import datetime
from typing import Any

from pydantic import Field

from app.scheduling.models import AcademicTask, StudySession
from app.workflows.lecture_notes.schemas import StrictModel


class PlanSetupInput(StrictModel):
    start: datetime
    end: datetime
    notion_database_id: str | None = None
    notion_mapping: dict[str, Any] | None = None
    calendar_id: str | None = None
    tasks: tuple[AcademicTask, ...] = ()


class TaskReviewInput(StrictModel):
    tasks: tuple[AcademicTask, ...] = Field(min_length=1)


class SessionAdjustmentInput(StrictModel):
    sessions: tuple[StudySession, ...]


class LockSessionInput(StrictModel):
    session_id: str
    locked: bool = True
