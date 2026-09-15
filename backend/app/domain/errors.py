class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400
    message = "The operation could not be completed."

    def __init__(self) -> None:
        super().__init__(self.message)


class InvalidWorkflowTransition(DomainError):
    code = "INVALID_WORKFLOW_TRANSITION"
    status_code = 409
    message = "This workflow state transition is not allowed."


class WorkflowNotFound(DomainError):
    code = "WORKFLOW_NOT_FOUND"
    status_code = 404
    message = "Workflow not found."


class WorkflowDefinitionDisabled(DomainError):
    code = "WORKFLOW_DEFINITION_DISABLED"
    status_code = 409
    message = "This workflow definition is disabled."


class ApprovalRequired(DomainError):
    code = "APPROVAL_REQUIRED"
    status_code = 409
    message = "Every proposed action needs an explicit approval."


class ApprovalAlreadyResolved(DomainError):
    code = "APPROVAL_ALREADY_RESOLVED"
    status_code = 409
    message = "This approval has already been resolved."


class ApprovalNotFound(DomainError):
    code = "APPROVAL_NOT_FOUND"
    status_code = 404
    message = "Approval not found."


class ApprovalPayloadMismatch(DomainError):
    code = "APPROVAL_PAYLOAD_MISMATCH"
    status_code = 409
    message = "The proposal changed. Review its exact current payload before approving."


class ConnectedAccountNotFound(DomainError):
    code = "CONNECTION_NOT_FOUND"
    status_code = 404
    message = "Connected account not found."


class ConnectedAccountAlreadyExists(DomainError):
    code = "CONNECTION_ALREADY_EXISTS"
    status_code = 409
    message = "This external account is already connected."


class InvalidPreferenceConfiguration(DomainError):
    code = "INVALID_PREFERENCES"
    status_code = 422
    message = "Check the timezone, study window, session lengths, and break duration."


class UnauthorizedResourceAccess(DomainError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404
    message = "Resource not found."


class ProjectNotFound(DomainError):
    code = "PROJECT_NOT_FOUND"
    status_code = 404
    message = "Project not found."


class SourceNotFound(DomainError):
    code = "SOURCE_NOT_FOUND"
    status_code = 404
    message = "Source not found."


class SourceTypeNotSupported(DomainError):
    code = "SOURCE_TYPE_NOT_SUPPORTED"
    status_code = 422
    message = "This source type is not available in this space."


class SourceContentRequired(DomainError):
    code = "SOURCE_CONTENT_REQUIRED"
    status_code = 422
    message = "Add source text or choose a document to process."


class SourceProcessingFailed(DomainError):
    code = "SOURCE_PROCESSING_FAILED"
    status_code = 422
    message = "Relay couldn't process this source. Check it and try again."


class TaskProposalNotFound(DomainError):
    code = "TASK_PROPOSAL_NOT_FOUND"
    status_code = 404
    message = "Task proposal not found."


class TaskProposalNeedsConfirmation(DomainError):
    code = "TASK_PROPOSAL_NEEDS_CONFIRMATION"
    status_code = 409
    message = "Confirm the unclear fields before accepting this task."


class TaskCreationFailed(DomainError):
    code = "TASK_CREATION_FAILED"
    status_code = 502
    message = "Relay couldn't create the selected task. Please retry."


class CredentialStorageUnavailable(DomainError):
    code = "CREDENTIAL_STORAGE_UNAVAILABLE"
    status_code = 503
    message = "Credential storage is not configured."


class OAuthNotConfigured(DomainError):
    code = "OAUTH_NOT_CONFIGURED"
    status_code = 501
    message = "Provider OAuth is not configured. You can continue with mock/local workflow paths."
