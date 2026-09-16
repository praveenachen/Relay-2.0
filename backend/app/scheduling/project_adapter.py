from datetime import UTC

from app.models.entities import ProjectTask, ProjectWorkspace
from app.scheduling.models import AcademicTask

_PRIORITY = {"LOW": 1, "MEDIUM": 3, "HIGH": 5}


def project_task_to_scheduler_input(
    task: ProjectTask, project: ProjectWorkspace
) -> AcademicTask | None:
    """Map the canonical task to the legacy solver contract without persisting a copy."""
    if task.status == "DONE" or task.due_date is None or task.estimate_minutes is None:
        return None
    deadline = task.due_date
    if deadline.tzinfo is None:
        # SQLite drops offsets while PostgreSQL preserves them. Relay stores
        # canonical task deadlines as UTC, so restore that invariant here.
        deadline = deadline.replace(tzinfo=UTC)
    return AcademicTask(
        id=str(task.id),
        title=task.title,
        course=project.name,
        deadline=deadline,
        estimated_minutes=task.estimate_minutes,
        priority=_PRIORITY.get(task.priority or "MEDIUM", 3),
        status=task.status.lower(),
    )
