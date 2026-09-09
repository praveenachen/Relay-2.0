"""Domain-neutral execution contract shared by local and future remote runtimes."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str = Field(min_length=1)
    payload: dict[str, JsonValue]
    idempotency_key: str = Field(min_length=1)


class ExecutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    status: ExecutionStatus
    result: dict[str, JsonValue] | None = None
    error_code: str | None = None
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RuntimeClient(Protocol):
    async def submit_execution(self, request: ExecutionRequest) -> ExecutionSnapshot: ...

    async def get_execution(self, execution_id: UUID) -> ExecutionSnapshot: ...

    async def cancel_execution(self, execution_id: UUID) -> ExecutionSnapshot: ...
