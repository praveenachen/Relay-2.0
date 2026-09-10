"""Domain-neutral execution contract shared by local and remote runtimes."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_run_id: UUID
    proposed_action_id: UUID
    action_type: str = Field(min_length=1)
    approved_payload: dict[str, JsonValue]
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    @property
    def operation(self) -> str:
        return self.action_type

    @property
    def payload(self) -> dict[str, JsonValue]:
        return self.approved_payload


class ExecutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    status: ExecutionStatus
    result: dict[str, JsonValue] | None = None
    error_code: str | None = None
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def failed_status_has_error(self) -> "ExecutionSnapshot":
        if self.status == ExecutionStatus.FAILED and not self.error_code:
            self.error_code = "RUNTIME_EXECUTION_FAILED"
        return self


class RuntimeClient(Protocol):
    async def submit_execution(self, request: ExecutionRequest) -> ExecutionSnapshot: ...

    async def get_execution(self, execution_id: UUID) -> ExecutionSnapshot: ...

    async def cancel_execution(self, execution_id: UUID) -> ExecutionSnapshot: ...
