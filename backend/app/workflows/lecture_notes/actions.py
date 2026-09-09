from app.connectors.notion import CreateNotionStudyPageAction, NotionStudyPageContent
from app.workflows.lecture_notes.schemas import LectureSummary

OPERATION = "create_notion_study_page"


def proposed_page(
    summary: LectureSummary,
    *,
    connection_id: str | None = None,
    destination_id: str | None = None,
    destination_title: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> CreateNotionStudyPageAction:
    return CreateNotionStudyPageAction(
        title=summary.title,
        connection_id=connection_id,
        parent_destination_id=destination_id,
        parent_destination_title=destination_title,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        content=NotionStudyPageContent(summary=summary),
    )
