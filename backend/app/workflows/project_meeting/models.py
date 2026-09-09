from typing import Literal

from pydantic import Field

from app.workflows.lecture_notes.schemas import StrictModel

ActionCategory = Literal[
    "GENERAL_TASK", "TECHNICAL_TASK", "DOCUMENTATION", "RESEARCH", "REVIEW_REQUEST"
]
Confidence = Literal["high", "medium", "low"]


class MeetingSourceReference(StrictModel):
    segment_id: str


class MeetingDecision(StrictModel):
    title: str
    description: str
    source_refs: list[MeetingSourceReference] = Field(default_factory=list)


class MeetingActionItem(StrictModel):
    title: str
    description: str
    owner_name: str | None = None
    deadline_text: str | None = None
    category: ActionCategory
    source_refs: list[MeetingSourceReference] = Field(default_factory=list)
    confidence: Confidence
    # Only meaningful for category == REVIEW_REQUEST: the raw transcript
    # phrase naming a PR or its author (e.g. "PR #12", "Sarah's PR"). The
    # model never invents a PR number; a deterministic regex later tries to
    # extract one from this text, and the action stays unresolved if it can't.
    pull_request_reference: str | None = None


class MeetingAnalysis(StrictModel):
    summary: str
    decisions: list[MeetingDecision] = Field(default_factory=list)
    action_items: list[MeetingActionItem] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
