from datetime import datetime, time
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.domain.enums import ApprovalStatus, ConnectionStatus, Provider, WorkflowStatus
from app.domain.errors import InvalidPreferenceConfiguration
from app.domain.preferences import validate_preferences


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PreferenceInput(InputModel):
    timezone: str = Field(max_length=100)
    earliest_study_time: time
    latest_study_time: time
    preferred_session_minutes: int = Field(ge=5, le=480)
    maximum_session_minutes: int = Field(ge=5, le=480)
    minimum_break_minutes: int = Field(ge=0, le=240)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        try:
            validate_preferences(
                self.timezone,
                self.earliest_study_time,
                self.latest_study_time,
                self.preferred_session_minutes,
                self.maximum_session_minutes,
                self.minimum_break_minutes,
            )
        except InvalidPreferenceConfiguration as error:
            raise ValueError(error.message) from error
        return self


class PreferenceRead(PreferenceInput, ReadModel):
    id: UUID
    user_id: UUID


class ProfileInput(InputModel):
    name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")


class DefinitionRead(ReadModel):
    id: UUID
    key: str
    name: str
    version: int
    description: str
    enabled: bool


class RunInput(InputModel):
    workflow_definition_id: UUID
    input_payload: dict[str, JsonValue] = Field(default_factory=dict)


class RunRead(ReadModel):
    id: UUID
    workflow_definition_id: UUID
    status: WorkflowStatus
    input_payload: dict[str, JsonValue]
    plan_payload: dict[str, JsonValue] | None
    result_payload: dict[str, JsonValue] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ApprovalInput(InputModel):
    approved_payload: dict[str, JsonValue]


class ApprovalRead(ReadModel):
    id: UUID
    workflow_run_id: UUID
    proposed_action_id: UUID
    status: ApprovalStatus
    original_payload: dict[str, JsonValue]
    approved_payload: dict[str, JsonValue] | None
    requested_at: datetime
    resolved_at: datetime | None


class ConnectionRead(ReadModel):
    id: UUID
    provider: Provider
    external_account_id: str
    display_name: str
    token_expires_at: datetime | None
    scopes: list[str]
    provider_metadata: dict[str, JsonValue]
    status: ConnectionStatus


class AuthorizationRead(BaseModel):
    authorization_url: str


class NotionDestinationRead(BaseModel):
    id: str
    title: str
    icon_url: str | None = None
    object_type: str = "page"


class NotionDestinationInput(InputModel):
    destination_id: str = Field(min_length=1, max_length=255)


class AuditRead(ReadModel):
    id: UUID
    event_type: str
    event_metadata: dict[str, JsonValue]
    created_at: datetime
