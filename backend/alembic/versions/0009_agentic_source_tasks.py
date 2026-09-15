"""Add project sources, internal tasks, and source-to-task workflow."""

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0009_agentic_source_tasks"
down_revision = "0008_project_product_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposed_action") as batch:
        batch.drop_constraint("actionprovider", type_="check")
        batch.create_check_constraint(
            "actionprovider",
            "provider IN ('GOOGLE_CALENDAR', 'NOTION', 'GITHUB', 'RELAY')",
        )
    op.create_table(
        "project_source",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "project_workspace_id",
            sa.Uuid(),
            sa.ForeignKey("project_workspace.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_source_project", "project_source", ["project_workspace_id"])
    op.create_table(
        "project_task",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "project_workspace_id",
            sa.Uuid(),
            sa.ForeignKey("project_workspace.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("estimate_minutes", sa.Integer()),
        sa.Column("priority", sa.String(10)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("project_source.id")),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("proposed_action_id", sa.Uuid(), sa.ForeignKey("proposed_action.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("proposed_action_id"),
    )
    op.create_index("ix_project_task_project", "project_task", ["project_workspace_id"])
    definitions = sa.table(
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
        definitions,
        [
            dict(
                id=UUID(int=4),
                key="source_to_tasks",
                name="Source capture",
                description="Turn project sources into reviewed task proposals.",
                version=1,
                enabled=True,
                created_at=instant,
                updated_at=instant,
            )
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_project_task_project", table_name="project_task")
    op.drop_table("project_task")
    op.drop_index("ix_project_source_project", table_name="project_source")
    op.drop_table("project_source")
    op.execute("DELETE FROM workflow_definition WHERE key = 'source_to_tasks' AND version = 1")
    with op.batch_alter_table("proposed_action") as batch:
        batch.drop_constraint("actionprovider", type_="check")
        batch.create_check_constraint(
            "actionprovider",
            "provider IN ('GOOGLE_CALENDAR', 'NOTION', 'GITHUB')",
        )
