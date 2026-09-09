"""Seed the three supported definitions once through versioned migrations."""

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0003_workflow_definitions"
down_revision = "0002_core_domain"
branch_labels = None
depends_on = None

DEFINITIONS = [
    ("lecture_to_notion", "Learn", "Turn lecture notes into structured Notion notes."),
    ("study_scheduler", "Plan", "Build a realistic study schedule from tasks and availability."),
    ("project_meeting", "Collaborate", "Turn meeting transcripts into shared action items."),
]


def upgrade() -> None:
    table = sa.table(
        "workflow_definition",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("version", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    op.bulk_insert(
        table,
        [
            dict(
                id=UUID(int=i),
                key=key,
                name=name,
                description=description,
                version=1,
                enabled=True,
                created_at=instant,
                updated_at=instant,
            )
            for i, (key, name, description) in enumerate(DEFINITIONS, 1)
        ],
    )


def downgrade() -> None:
    # A referenced definition cannot be removed while runs still exist.
    op.execute(
        "DELETE FROM workflow_definition WHERE version = 1 AND "
        "key IN ('lecture_to_notion', 'study_scheduler', 'project_meeting')"
    )
