from app.domain.enums import WorkflowStatus
from app.runtime.client import ExecutionStatus
from app.runtime.state import workflow_status_for_action_results, workflow_status_for_runtime


def test_runtime_state_mapping() -> None:
    assert workflow_status_for_runtime(ExecutionStatus.QUEUED) == WorkflowStatus.QUEUED
    assert workflow_status_for_runtime(ExecutionStatus.RUNNING) == WorkflowStatus.EXECUTING
    assert workflow_status_for_runtime(ExecutionStatus.SUCCEEDED) == WorkflowStatus.COMPLETED
    assert workflow_status_for_runtime(ExecutionStatus.FAILED) == WorkflowStatus.FAILED
    assert workflow_status_for_runtime(ExecutionStatus.CANCELLED) == WorkflowStatus.CANCELLED


def test_multi_action_state_mapping_preserves_partial_completion() -> None:
    assert (
        workflow_status_for_action_results([ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED])
        == WorkflowStatus.PARTIALLY_COMPLETED
    )
