"""PLAN integration calendar and task source state."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0006_plan_integration"
down_revision = "0005_notion_integration"
branch_labels = None
depends_on = None
payload = sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    op.create_table(
        "google_calendar",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "connection_id", sa.Uuid(), sa.ForeignKey("connected_account.id"), nullable=False
        ),
        sa.Column("provider_calendar_id", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("time_zone", sa.String(100)),
        sa.Column("primary", sa.Boolean(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connection_id", "provider_calendar_id"),
    )
    op.create_index(
        "ix_google_calendar_user_connection", "google_calendar", ["user_id", "connection_id"]
    )
    op.create_table(
        "notion_task_database",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "connection_id", sa.Uuid(), sa.ForeignKey("connected_account.id"), nullable=False
        ),
        sa.Column("provider_database_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("property_mapping", payload, nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connection_id", "provider_database_id"),
    )
    op.create_index(
        "ix_notion_task_database_user_connection",
        "notion_task_database",
        ["user_id", "connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notion_task_database_user_connection", table_name="notion_task_database")
    op.drop_table("notion_task_database")
    op.drop_index("ix_google_calendar_user_connection", table_name="google_calendar")
    op.drop_table("google_calendar")
