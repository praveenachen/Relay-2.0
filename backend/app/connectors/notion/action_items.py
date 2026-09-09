from datetime import date
from typing import Any, Literal

from app.connectors.notion.client import notion_rich_text
from app.workflows.lecture_notes.schemas import StrictModel


class NotionActionItemPropertyMapping(StrictModel):
    """Configures how a COLLABORATE action item is written into a Notion
    database's properties. Separate from NotionTaskPropertyMapping (PLAN),
    which reads tasks rather than writing them, and maps different field
    names (course/estimate vs. description/owner)."""

    title: str
    description: str | None = None
    owner: str | None = None
    deadline: str | None = None
    status: str | None = None
    status_property_type: Literal["select", "status"] = "status"
    default_status: str = "To Do"


def build_task_properties(
    mapping: NotionActionItemPropertyMapping,
    *,
    title: str,
    description: str | None,
    owner_name: str | None,
    deadline_date: date | None,
) -> dict[str, Any]:
    """Deterministic property construction -- no model call happens here.
    Unmapped fields are simply omitted from properties; the full content
    still goes into the page body via NotionStudyPageMapper-style blocks so
    nothing is lost even when a database has fewer structured fields."""
    properties: dict[str, Any] = {mapping.title: {"title": notion_rich_text(title[:1900])}}
    if mapping.description and description:
        properties[mapping.description] = {"rich_text": notion_rich_text(description[:1900])}
    if mapping.owner and owner_name:
        properties[mapping.owner] = {"rich_text": notion_rich_text(owner_name[:1900])}
    if mapping.deadline and deadline_date:
        properties[mapping.deadline] = {"date": {"start": deadline_date.isoformat()}}
    if mapping.status:
        properties[mapping.status] = {
            mapping.status_property_type: {"name": mapping.default_status}
        }
    return properties
