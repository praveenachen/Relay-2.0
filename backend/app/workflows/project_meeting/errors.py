from app.domain.errors import DomainError


class CollaborateWorkflowInvalidState(DomainError):
    code = "COLLABORATE_WORKFLOW_INVALID_STATE"
    status_code = 409
    message = "The COLLABORATE workflow is not in a state that allows this operation."


class EmptyTranscript(DomainError):
    code = "EMPTY_TRANSCRIPT"
    status_code = 422
    message = "The transcript has no usable content."


class ProjectRequired(DomainError):
    code = "PROJECT_REQUIRED"
    status_code = 422
    message = "Select a project before analyzing a transcript."


class ActionItemsUnresolved(DomainError):
    code = "ACTION_ITEMS_UNRESOLVED"
    status_code = 422
    message = (
        "One or more action items still need an owner, repository, or pull request "
        "resolved before they can be proposed."
    )
