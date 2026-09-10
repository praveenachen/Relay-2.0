from app.domain.enums import WorkflowStatus
from app.runtime.client import ExecutionStatus

_RUNTIME_TO_WORKFLOW = {
    ExecutionStatus.QUEUED: WorkflowStatus.QUEUED,
    ExecutionStatus.RUNNING: WorkflowStatus.EXECUTING,
    ExecutionStatus.SUCCEEDED: WorkflowStatus.COMPLETED,
    ExecutionStatus.PARTIAL: WorkflowStatus.PARTIALLY_COMPLETED,
    ExecutionStatus.FAILED: WorkflowStatus.FAILED,
    ExecutionStatus.CANCELLED: WorkflowStatus.CANCELLED,
}


def workflow_status_for_runtime(status: ExecutionStatus) -> WorkflowStatus:
    return _RUNTIME_TO_WORKFLOW[status]


def workflow_status_for_action_results(statuses: list[ExecutionStatus]) -> WorkflowStatus:
    if not statuses:
        return WorkflowStatus.FAILED
    if all(status == ExecutionStatus.SUCCEEDED for status in statuses):
        return WorkflowStatus.COMPLETED
    if any(status == ExecutionStatus.SUCCEEDED for status in statuses):
        return WorkflowStatus.PARTIALLY_COMPLETED
    if all(status == ExecutionStatus.CANCELLED for status in statuses):
        return WorkflowStatus.CANCELLED
    return WorkflowStatus.FAILED


def runtime_status_is_terminal(status: ExecutionStatus) -> bool:
    return status in {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.PARTIAL,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }
