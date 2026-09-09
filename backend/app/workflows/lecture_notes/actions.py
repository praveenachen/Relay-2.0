from app.connectors.notion import CreateNotionStudyPageAction, NotionStudyPageContent
from app.workflows.lecture_notes.schemas import LectureSummary

OPERATION = "create_notion_study_page"


def proposed_page(summary: LectureSummary) -> CreateNotionStudyPageAction:
    return CreateNotionStudyPageAction(
        title=summary.title,
        content=NotionStudyPageContent(summary=summary),
    )
