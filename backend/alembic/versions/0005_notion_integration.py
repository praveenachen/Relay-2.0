"""Notion OAuth state, metadata and destination selection."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005_notion_integration"
down_revision = "0004_learn"
branch_labels = None
depends_on = None
payload = sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("connected_account") as batch:
        batch.add_column(sa.Column("provider_metadata", payload, nullable=True))
    op.execute("UPDATE connected_account SET provider_metadata = '{}'")
    with op.batch_alter_table("connected_account") as batch:
        batch.alter_column("provider_metadata", nullable=False)
    op.create_table(
        "oauth_state",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "provider", sa.Enum("GOOGLE", "NOTION", "GITHUB", native_enum=False), nullable=False
        ),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_state_user_provider", "oauth_state", ["user_id", "provider"])
    op.create_table(
        "notion_destination",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "connection_id", sa.Uuid(), sa.ForeignKey("connected_account.id"), nullable=False
        ),
        sa.Column("provider_page_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("icon_url", sa.String(2048)),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connection_id", "provider_page_id"),
    )
    op.create_index(
        "ix_notion_destination_user_connection",
        "notion_destination",
        ["user_id", "connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notion_destination_user_connection", table_name="notion_destination")
    op.drop_table("notion_destination")
    op.drop_index("ix_oauth_state_user_provider", table_name="oauth_state")
    op.drop_table("oauth_state")
    with op.batch_alter_table("connected_account") as batch:
        batch.drop_column("provider_metadata")
