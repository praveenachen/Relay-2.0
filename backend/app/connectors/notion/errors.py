from app.domain.errors import DomainError


class NotionNotConnected(DomainError):
    code = "NOTION_NOT_CONNECTED"
    status_code = 409
    message = "Connect Notion before publishing these notes."


class NotionAuthorizationFailed(DomainError):
    code = "NOTION_AUTHORIZATION_FAILED"
    status_code = 401
    message = "Your Notion connection needs attention. Reconnect Notion and try again."


class NotionPermissionDenied(DomainError):
    code = "NOTION_PERMISSION_DENIED"
    status_code = 403
    message = "Relay cannot access the selected Notion destination. Choose another destination."


class NotionDestinationNotFound(DomainError):
    code = "NOTION_DESTINATION_NOT_FOUND"
    status_code = 404
    message = "Relay could not find the selected Notion destination."


class NotionTaskDatabaseNotFound(DomainError):
    code = "NOTION_TASK_DATABASE_NOT_FOUND"
    status_code = 404
    message = "Relay could not find the selected Notion task database."


class NotionRateLimited(DomainError):
    code = "NOTION_RATE_LIMITED"
    status_code = 429
    message = "Notion is rate limiting Relay. Try again shortly."

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__()


class NotionValidationFailed(DomainError):
    code = "NOTION_VALIDATION_FAILED"
    status_code = 422
    message = "Notion rejected the study page format."


class NotionUnavailable(DomainError):
    code = "NOTION_UNAVAILABLE"
    status_code = 503
    message = "Notion is temporarily unavailable. Try again later."


class NotionRequestTimeout(DomainError):
    code = "NOTION_REQUEST_TIMEOUT"
    status_code = 504
    message = "Relay could not confirm whether Notion created the page."


class NotionPublishFailed(DomainError):
    code = "NOTION_PUBLISH_FAILED"
    status_code = 502
    message = "Relay could not publish the study page to Notion."


class MockNotionFailure(DomainError):
    code = "MOCK_NOTION_FAILED"
    status_code = 502
    message = "Simulated Notion publishing failed. No page was created."
