from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.runtime.client import ExecutionRequest


def valid_request() -> dict[str, object]:
    run_id = uuid4()
    action_id = uuid4()
    return {
        "workflow_run_id": run_id,
        "proposed_action_id": action_id,
        "action_type": "example",
        "approved_payload": {"title": "Approved"},
        "idempotency_key": f"run:{run_id}:{action_id}",
        "correlation_id": f"relay:{run_id}:{action_id}",
    }


def test_request_rejects_missing_idempotency_key() -> None:
    payload = valid_request()
    payload.pop("idempotency_key")
    with pytest.raises(ValidationError):
        ExecutionRequest.model_validate(payload)


def test_request_rejects_unknown_fields() -> None:
    payload = valid_request()
    payload["approved"] = True
    with pytest.raises(ValidationError):
        ExecutionRequest.model_validate(payload)


def test_request_exposes_existing_operation_and_payload_aliases() -> None:
    request = ExecutionRequest.model_validate(valid_request())
    assert request.operation == "example"
    assert request.payload == {"title": "Approved"}
