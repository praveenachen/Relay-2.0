"""COLLABORATE project context and workflow run linkage."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0007_collaborate_integration"
down_revision = "0006_plan_integration"
branch_labels = None
depends_on = None
payload = sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    op.create_table(
        "project_workspace",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("course", sa.String(200)),
        sa.Column("notion_database_id", sa.String(255)),
        sa.Column("notion_property_mapping", payload),
        sa.Column("github_repository_owner", sa.String(255)),
        sa.Column("github_repository_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_workspace_user", "project_workspace", ["user_id"])
    op.create_table(
        "project_member",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_workspace_id", sa.Uuid(), sa.ForeignKey("project_workspace.id"), nullable=False
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("notion_identity", sa.String(255)),
        sa.Column("github_username", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_member_workspace", "project_member", ["project_workspace_id"])
    with op.batch_alter_table("workflow_run") as batch:
        batch.add_column(
            sa.Column(
                "project_workspace_id",
                sa.Uuid(),
                sa.ForeignKey("project_workspace.id"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("workflow_run") as batch:
        batch.drop_column("project_workspace_id")
    op.drop_index("ix_project_member_workspace", table_name="project_member")
    op.drop_table("project_member")
    op.drop_index("ix_project_workspace_user", table_name="project_workspace")
    op.drop_table("project_workspace")
