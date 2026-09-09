from datetime import datetime
from typing import Any, Literal

from app.scheduling.models import AcademicTask
from app.workflows.lecture_notes.schemas import StrictModel


class NotionTaskPropertyMapping(StrictModel):
    title: str
    course: str | None = None
    deadline: str
    priority: str | None = None
    estimated_minutes: str
    status: str | None = None
    completed_statuses: tuple[str, ...] = ("Done", "Complete", "Completed")
    estimate_unit: Literal["minutes", "hours"] = "minutes"


class TaskMappingIssue(StrictModel):
    code: str
    message: str
    notion_page_id: str | None = None
    field: str | None = None


class NotionTaskImportResult(StrictModel):
    tasks: tuple[AcademicTask, ...]
    issues: tuple[TaskMappingIssue, ...] = ()


def _plain_text(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    kind = value.get("type")
    if kind in {"title", "rich_text"}:
        parts = value.get(kind, [])
        text = "".join(
            part.get("plain_text", "") for part in parts if isinstance(part, dict)
        ).strip()
        return text or None
    if kind == "select" and isinstance(value.get("select"), dict):
        raw = value["select"].get("name")
        return raw if isinstance(raw, str) else None
    if kind == "status" and isinstance(value.get("status"), dict):
        raw = value["status"].get("name")
        return raw if isinstance(raw, str) else None
    if kind == "number" and value.get("number") is not None:
        return str(value["number"])
    return None


def _date(value: Any) -> datetime | None:
    if not isinstance(value, dict) or value.get("type") != "date":
        return None
    raw = value.get("date")
    if not isinstance(raw, dict) or not isinstance(raw.get("start"), str):
        return None
    try:
        parsed = datetime.fromisoformat(raw["start"].replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _number(value: Any) -> float | None:
    if isinstance(value, dict) and value.get("type") == "number":
        raw = value.get("number")
        return float(raw) if isinstance(raw, int | float) else None
    text = _plain_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class NotionTaskMapper:
    def __init__(self, mapping: NotionTaskPropertyMapping):
        self.mapping = mapping

    def map_pages(self, pages: list[dict[str, Any]]) -> NotionTaskImportResult:
        tasks: list[AcademicTask] = []
        issues: list[TaskMappingIssue] = []
        for page in pages:
            page_id = page.get("id") if isinstance(page.get("id"), str) else None
            raw_properties = page.get("properties")
            properties: dict[str, Any] = raw_properties if isinstance(raw_properties, dict) else {}
            status = self._text(properties, self.mapping.status)
            if status and status.lower() in {
                item.lower() for item in self.mapping.completed_statuses
            }:
                continue
            title = self._text(properties, self.mapping.title)
            deadline = _date(properties.get(self.mapping.deadline))
            estimate = _number(properties.get(self.mapping.estimated_minutes))
            if not title:
                issues.append(
                    TaskMappingIssue(
                        code="TASK_TITLE_MISSING",
                        message="Task title is missing.",
                        notion_page_id=page_id,
                        field=self.mapping.title,
                    )
                )
                continue
            if deadline is None:
                issues.append(
                    TaskMappingIssue(
                        code="TASK_DEADLINE_MISSING",
                        message="Task deadline is missing or invalid.",
                        notion_page_id=page_id,
                        field=self.mapping.deadline,
                    )
                )
                continue
            if estimate is None or estimate <= 0:
                issues.append(
                    TaskMappingIssue(
                        code="TASK_ESTIMATE_MISSING",
                        message="Task estimate is missing or invalid.",
                        notion_page_id=page_id,
                        field=self.mapping.estimated_minutes,
                    )
                )
                continue
            priority = (
                int(_number(properties.get(self.mapping.priority)) or 3)
                if self.mapping.priority
                else 3
            )
            priority = min(5, max(1, priority))
            minutes = int(estimate * 60) if self.mapping.estimate_unit == "hours" else int(estimate)
            tasks.append(
                AcademicTask(
                    id=page_id or title,
                    title=title,
                    course=self._text(properties, self.mapping.course),
                    deadline=deadline,
                    estimated_minutes=minutes,
                    priority=priority,
                    status=status or "todo",
                )
            )
        return NotionTaskImportResult(tasks=tuple(tasks), issues=tuple(issues))

    def _text(self, properties: dict[str, Any], name: str | None) -> str | None:
        if not name:
            return None
        return _plain_text(properties.get(name))
