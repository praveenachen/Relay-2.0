import pytest
from pydantic import ValidationError

from app.runtime.client import ExecutionRequest


def test_request_rejects_missing_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        ExecutionRequest.model_validate({"operation": "example", "payload": {}})


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExecutionRequest.model_validate(
            {"operation": "example", "payload": {}, "idempotency_key": "abc", "approved": True}
        )
