from pydantic import Field

from app.connectors.google.schemas import CreateCalendarStudyBlockAction
from app.workflows.lecture_notes.schemas import StrictModel

OPERATION = "create_google_calendar_study_blocks"


class CreateCalendarStudyPlanAction(StrictModel):
    connection_id: str | None = None
    calendar_id: str
    calendar_summary: str | None = None
    events: tuple[CreateCalendarStudyBlockAction, ...] = Field(min_length=1)
