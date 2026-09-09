from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    column,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import (
    ActionProvider,
    ActionStatus,
    ApprovalStatus,
    ConnectionStatus,
    Provider,
    RiskLevel,
    WorkflowStatus,
)


def now() -> datetime:
    return datetime.now(UTC)


def enum_type(enum: type[StrEnum]) -> Enum:
    return Enum(enum, native_enum=False, create_constraint=True, name=enum.__name__.lower())


PAYLOAD = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Identity:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(SQLAlchemyBaseUserTableUUID, Timestamps, Base):
    __tablename__ = "user"
    __table_args__ = (Index("uq_user_email_normalized", func.lower(column("email")), unique=True),)
    name: Mapped[str] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    __tablename__ = "accesstoken"


class UserPreference(Identity, Timestamps, Base):
    __tablename__ = "user_preference"
    __table_args__ = (
        CheckConstraint(
            "preferred_session_minutes >= 5 "
            "AND preferred_session_minutes <= maximum_session_minutes "
            "AND maximum_session_minutes <= 480",
            name="session_lengths",
        ),
        CheckConstraint(
            "minimum_break_minutes >= 0 AND minimum_break_minutes <= 240", name="break_minutes"
        ),
        CheckConstraint("earliest_study_time < latest_study_time", name="study_window"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"), unique=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    earliest_study_time: Mapped[time] = mapped_column(Time, default=time(8))
    latest_study_time: Mapped[time] = mapped_column(Time, default=time(22))
    preferred_session_minutes: Mapped[int] = mapped_column(default=50)
    maximum_session_minutes: Mapped[int] = mapped_column(default=90)
    minimum_break_minutes: Mapped[int] = mapped_column(default=10)


class ConnectedAccount(Identity, Timestamps, Base):
    __tablename__ = "connected_account"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_account_id"),
        Index("ix_connection_user_provider", "user_id", "provider"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    provider: Mapped[Provider] = mapped_column(enum_type(Provider))
    external_account_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(PAYLOAD, default=list)
    status: Mapped[ConnectionStatus] = mapped_column(enum_type(ConnectionStatus))


class WorkflowDefinition(Identity, Timestamps, Base):
    __tablename__ = "workflow_definition"
    __table_args__ = (UniqueConstraint("key", "version"),)
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(default=1)
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowRun(Identity, Timestamps, Base):
    __tablename__ = "workflow_run"
    __table_args__ = (Index("ix_run_user_created", "user_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    workflow_definition_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_definition.id"))
    status: Mapped[WorkflowStatus] = mapped_column(
        enum_type(WorkflowStatus), index=True, default=WorkflowStatus.DRAFT
    )
    runtime_execution_id: Mapped[UUID | None] = mapped_column(Uuid)
    input_payload: Mapped[dict[str, Any]] = mapped_column(PAYLOAD, default=dict)
    plan_payload: Mapped[dict[str, Any] | None] = mapped_column(PAYLOAD)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(PAYLOAD)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProposedAction(Identity, Timestamps, Base):
    __tablename__ = "proposed_action"
    __table_args__ = (UniqueConstraint("id", "workflow_run_id"),)
    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_run.id"), index=True)
    provider: Mapped[ActionProvider] = mapped_column(enum_type(ActionProvider))
    action_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(PAYLOAD)
    risk_level: Mapped[RiskLevel] = mapped_column(enum_type(RiskLevel), default=RiskLevel.LOW)
    status: Mapped[ActionStatus] = mapped_column(
        enum_type(ActionStatus), default=ActionStatus.PROPOSED
    )


class ApprovalRequest(Identity, Base):
    __tablename__ = "approval_request"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposed_action_id", "workflow_run_id"],
            ["proposed_action.id", "proposed_action.workflow_run_id"],
        ),
        CheckConstraint(
            "(status = 'PENDING' AND resolved_at IS NULL AND resolved_by IS NULL) "
            "OR (status != 'PENDING' AND resolved_at IS NOT NULL)",
            name="resolution_time",
        ),
        CheckConstraint(
            "status != 'APPROVED' OR (approved_payload IS NOT NULL AND resolved_by IS NOT NULL)",
            name="approved_snapshot",
        ),
    )
    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_run.id"), index=True)
    proposed_action_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        enum_type(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    original_payload: Mapped[dict[str, Any]] = mapped_column(PAYLOAD)
    approved_payload: Mapped[dict[str, Any] | None] = mapped_column(PAYLOAD, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"))


class ExternalArtifact(Identity, Base):
    __tablename__ = "external_artifact"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposed_action_id", "workflow_run_id"],
            ["proposed_action.id", "proposed_action.workflow_run_id"],
        ),
        UniqueConstraint("connected_account_id", "artifact_type", "external_id"),
    )
    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_run.id"))
    proposed_action_id: Mapped[UUID] = mapped_column(Uuid)
    connected_account_id: Mapped[UUID] = mapped_column(ForeignKey("connected_account.id"))
    provider: Mapped[ActionProvider] = mapped_column(enum_type(ActionProvider))
    artifact_type: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str] = mapped_column(String(255))
    external_url: Mapped[str] = mapped_column(String(2048))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_run_created", "workflow_run_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    workflow_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_run.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", PAYLOAD, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
