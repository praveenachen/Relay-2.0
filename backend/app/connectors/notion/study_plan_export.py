from typing import Any

from app.connectors.notion.client import notion_rich_text
from app.scheduling.models import AcademicTask

# Relay owns this schema outright -- unlike Collaborate's action-item sync,
# which writes into a database the user already configured (and can drift
# out from under the mapping), PLAN creates a brand-new database per export,
# so there's nothing to validate against and no mapping to configure.
STUDY_PLAN_DATABASE_PROPERTIES: dict[str, Any] = {
    "Title": {"title": {}},
    "Category": {"rich_text": {}},
    "Deadline": {"date": {}},
    "Estimated minutes": {"number": {}},
    "Priority": {"number": {}},
    "Status": {"rich_text": {}},
}


def build_task_row_properties(task: AcademicTask) -> dict[str, Any]:
    return {
        "Title": {"title": notion_rich_text(task.title[:1900])},
        "Category": {"rich_text": notion_rich_text(task.course[:1900] if task.course else "")},
        "Deadline": {"date": {"start": task.deadline.isoformat()}},
        "Estimated minutes": {"number": task.estimated_minutes},
        "Priority": {"number": task.priority},
        "Status": {"rich_text": notion_rich_text(task.status[:1900])},
    }
