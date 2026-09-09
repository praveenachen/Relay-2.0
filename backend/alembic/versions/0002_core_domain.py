"""Core domain, account persistence, and revocable sessions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_core_domain"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)
    op.create_table(
        "workflow_definition",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definition")),
        sa.UniqueConstraint("key", "version", name=op.f("uq_workflow_definition_key")),
    )
    op.create_table(
        "accesstoken",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=43), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_accesstoken_user_id_user"), ondelete="cascade"
        ),
        sa.PrimaryKeyConstraint("token", name=op.f("pk_accesstoken")),
    )
    op.create_index(op.f("ix_accesstoken_created_at"), "accesstoken", ["created_at"], unique=False)
    op.create_table(
        "connected_account",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "GOOGLE",
                "NOTION",
                "GITHUB",
                name="provider",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scopes",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CONNECTED",
                "EXPIRED",
                "REVOKED",
                "ERROR",
                name="connectionstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_connected_account_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connected_account")),
        sa.UniqueConstraint(
            "user_id", "provider", "external_account_id", name=op.f("uq_connected_account_user_id")
        ),
    )
    op.create_index(
        "ix_connection_user_provider", "connected_account", ["user_id", "provider"], unique=False
    )
    op.create_table(
        "user_preference",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("earliest_study_time", sa.Time(), nullable=False),
        sa.Column("latest_study_time", sa.Time(), nullable=False),
        sa.Column("preferred_session_minutes", sa.Integer(), nullable=False),
        sa.Column("maximum_session_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_break_minutes", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "earliest_study_time < latest_study_time", name=op.f("ck_user_preference_study_window")
        ),
        sa.CheckConstraint(
            "minimum_break_minutes >= 0 AND minimum_break_minutes <= 240",
            name=op.f("ck_user_preference_break_minutes"),
        ),
        sa.CheckConstraint(
            "preferred_session_minutes >= 5 "
            "AND preferred_session_minutes <= maximum_session_minutes "
            "AND maximum_session_minutes <= 480",
            name=op.f("ck_user_preference_session_lengths"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_user_preference_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preference")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_preference_user_id")),
    )
    op.create_table(
        "workflow_run",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "ANALYZING",
                "PLAN_READY",
                "AWAITING_APPROVAL",
                "APPROVED",
                "QUEUED",
                "EXECUTING",
                "COMPLETED",
                "PARTIALLY_COMPLETED",
                "FAILED",
                "REJECTED",
                "CANCELLED",
                name="workflowstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("runtime_execution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "input_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "plan_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "result_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_workflow_run_user_id_user")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow_definition.id"],
            name=op.f("fk_workflow_run_workflow_definition_id_workflow_definition"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_run")),
    )
    op.create_index("ix_run_user_created", "workflow_run", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_workflow_run_status"), "workflow_run", ["status"], unique=False)
    op.create_table(
        "audit_event",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_audit_event_user_id_user")),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_run.id"],
            name=op.f("fk_audit_event_workflow_run_id_workflow_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        "ix_audit_run_created", "audit_event", ["workflow_run_id", "created_at"], unique=False
    )
    op.create_table(
        "proposed_action",
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "GOOGLE_CALENDAR",
                "NOTION",
                "GITHUB",
                name="actionprovider",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            sa.Enum(
                "LOW", "MEDIUM", "HIGH", name="risklevel", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PROPOSED",
                "EDITED",
                "APPROVED",
                "REJECTED",
                "QUEUED",
                "EXECUTING",
                "COMPLETED",
                "FAILED",
                name="actionstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_run.id"],
            name=op.f("fk_proposed_action_workflow_run_id_workflow_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposed_action")),
        sa.UniqueConstraint("id", "workflow_run_id", name=op.f("uq_proposed_action_id")),
    )
    op.create_index(
        op.f("ix_proposed_action_workflow_run_id"),
        "proposed_action",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_table(
        "approval_request",
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_action_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "EXPIRED",
                name="approvalstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "original_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "approved_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(status = 'PENDING' AND resolved_at IS NULL AND resolved_by IS NULL) "
            "OR (status != 'PENDING' AND resolved_at IS NOT NULL)",
            name=op.f("ck_approval_request_resolution_time"),
        ),
        sa.CheckConstraint(
            "status != 'APPROVED' OR (approved_payload IS NOT NULL AND resolved_by IS NOT NULL)",
            name=op.f("ck_approval_request_approved_snapshot"),
        ),
        sa.ForeignKeyConstraint(
            ["proposed_action_id", "workflow_run_id"],
            ["proposed_action.id", "proposed_action.workflow_run_id"],
            name=op.f("fk_approval_request_proposed_action_id_proposed_action"),
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["user.id"], name=op.f("fk_approval_request_resolved_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_run.id"],
            name=op.f("fk_approval_request_workflow_run_id_workflow_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_request")),
        sa.UniqueConstraint(
            "proposed_action_id", name=op.f("uq_approval_request_proposed_action_id")
        ),
    )
    op.create_index(
        op.f("ix_approval_request_workflow_run_id"),
        "approval_request",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_table(
        "external_artifact",
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_action_id", sa.Uuid(), nullable=False),
        sa.Column("connected_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "GOOGLE_CALENDAR",
                "NOTION",
                "GITHUB",
                name="actionprovider",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_url", sa.String(length=2048), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connected_account_id"],
            ["connected_account.id"],
            name=op.f("fk_external_artifact_connected_account_id_connected_account"),
        ),
        sa.ForeignKeyConstraint(
            ["proposed_action_id", "workflow_run_id"],
            ["proposed_action.id", "proposed_action.workflow_run_id"],
            name=op.f("fk_external_artifact_proposed_action_id_proposed_action"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_run.id"],
            name=op.f("fk_external_artifact_workflow_run_id_workflow_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_artifact")),
        sa.UniqueConstraint(
            "connected_account_id",
            "artifact_type",
            "external_id",
            name=op.f("uq_external_artifact_connected_account_id"),
        ),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_external_artifact_idempotency_key")),
    )

    op.create_index("uq_user_email_normalized", "user", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_user_email_normalized", table_name="user")
    op.drop_table("external_artifact")
    op.drop_index(op.f("ix_approval_request_workflow_run_id"), table_name="approval_request")
    op.drop_table("approval_request")
    op.drop_index(op.f("ix_proposed_action_workflow_run_id"), table_name="proposed_action")
    op.drop_table("proposed_action")
    op.drop_index("ix_audit_run_created", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index(op.f("ix_workflow_run_status"), table_name="workflow_run")
    op.drop_index("ix_run_user_created", table_name="workflow_run")
    op.drop_table("workflow_run")
    op.drop_table("user_preference")
    op.drop_index("ix_connection_user_provider", table_name="connected_account")
    op.drop_table("connected_account")
    op.drop_index(op.f("ix_accesstoken_created_at"), table_name="accesstoken")
    op.drop_table("accesstoken")
    op.drop_table("workflow_definition")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
