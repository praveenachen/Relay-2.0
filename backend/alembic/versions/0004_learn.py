"""Private source documents and local executions; simulated artifacts have no account."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004_learn"
down_revision = "0003_workflow_definitions"
branch_labels = None
depends_on = None
payload = sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("external_artifact") as batch:
        batch.alter_column("connected_account_id", existing_type=sa.Uuid(), nullable=True)
    op.create_table(
        "source_document",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_run.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(32), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("parsed_payload", payload),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_run_id"),
        sa.UniqueConstraint("storage_key"),
        sa.CheckConstraint("status IN ('UPLOADED', 'PARSED', 'FAILED')", name="source_status"),
    )
    op.create_index("ix_source_document_user_id", "source_document", ["user_id"])
    op.create_table(
        "local_execution",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("request_payload", payload, nullable=False),
        sa.Column("snapshot", payload, nullable=False),
    )


def downgrade() -> None:
    # Deliberately refuses if simulated artifacts still exist: do not silently delete results.
    op.drop_table("local_execution")
    op.drop_table("source_document")
    with op.batch_alter_table("external_artifact") as batch:
        batch.alter_column("connected_account_id", existing_type=sa.Uuid(), nullable=False)
