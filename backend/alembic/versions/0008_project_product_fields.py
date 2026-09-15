"""Add personal project-management fields to project workspaces."""

import sqlalchemy as sa

from alembic import op

revision = "0008_project_product_fields"
down_revision = "0007_collaborate_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_workspace") as batch:
        batch.add_column(
            sa.Column("space", sa.String(20), nullable=False, server_default="PERSONAL")
        )
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_workspace") as batch:
        batch.drop_column("deadline")
        batch.drop_column("description")
        batch.drop_column("space")
