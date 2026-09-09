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


class CredentialStorageUnavailable(DomainError):
    code = "CREDENTIAL_STORAGE_UNAVAILABLE"
    status_code = 503
    message = "Credential storage is not configured."


class OAuthNotConfigured(DomainError):
    code = "OAUTH_NOT_CONFIGURED"
    status_code = 501
    message = "Provider OAuth is not implemented yet. You can continue without connecting tools."
