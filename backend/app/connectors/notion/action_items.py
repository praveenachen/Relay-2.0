from datetime import date
from typing import Any, Literal

from app.connectors.notion.client import notion_rich_text
from app.workflows.lecture_notes.schemas import StrictModel


class NotionActionItemPropertyMapping(StrictModel):
    """Configures how a COLLABORATE action item is written into a Notion
    database the user already configured. Separate from PLAN's export
    (study_plan_export.py), which creates its own database with a fixed,
    Relay-controlled schema and needs no user-provided mapping."""

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
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic property construction -- no model call happens here.
    Unmapped fields are simply omitted from properties; the full content
    still goes into the page body via NotionStudyPageMapper-style blocks so
    nothing is lost even when a database has fewer structured fields.

    `schema` is the database's live `properties` dict from Notion's
    `/v1/databases/{id}` response, when available. A configured mapping can
    drift from the real database (renamed/removed column, or a status
    column that's actually `select` vs `status`), and Notion rejects the
    whole page write when that happens. When we have the real schema, we
    only write properties that actually exist, with their real type,
    rather than trusting the mapping blindly."""
    schema_properties: dict[str, Any] = schema or {}

    def resolve_type(name: str, configured_type: str) -> str | None:
        if not schema_properties:
            return configured_type
        prop = schema_properties.get(name)
        return prop.get("type") if isinstance(prop, dict) else None

    title_name = mapping.title
    if schema_properties:
        actual_title = next(
            (
                name
                for name, prop in schema_properties.items()
                if isinstance(prop, dict) and prop.get("type") == "title"
            ),
            None,
        )
        # Every Notion database has exactly one title property; if the
        # configured name doesn't match it, use the real one so the write
        # never fails over a stale/renamed title column.
        if actual_title:
            title_name = actual_title
    properties: dict[str, Any] = {title_name: {"title": notion_rich_text(title[:1900])}}

    if mapping.description and description and resolve_type(mapping.description, "rich_text"):
        properties[mapping.description] = {"rich_text": notion_rich_text(description[:1900])}
    if mapping.owner and owner_name and resolve_type(mapping.owner, "rich_text"):
        properties[mapping.owner] = {"rich_text": notion_rich_text(owner_name[:1900])}
    if mapping.deadline and deadline_date and resolve_type(mapping.deadline, "date"):
        properties[mapping.deadline] = {"date": {"start": deadline_date.isoformat()}}
    if mapping.status:
        status_type = resolve_type(mapping.status, mapping.status_property_type)
        if status_type in ("select", "status"):
            properties[mapping.status] = {status_type: {"name": mapping.default_status}}
    return properties
