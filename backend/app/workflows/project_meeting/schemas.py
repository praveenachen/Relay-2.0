from uuid import UUID

from app.workflows.lecture_notes.schemas import StrictModel
from app.workflows.project_meeting.actions import PlannedAction


class CreateCollaborateRunInput(StrictModel):
    project_id: UUID


class ActionItemsInput(StrictModel):
    action_items: tuple[PlannedAction, ...]
