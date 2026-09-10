from app.domain.errors import DomainError


class RuntimeUnavailable(DomainError):
    code = "RUNTIME_UNAVAILABLE"
    status_code = 503
    message = "Agent Runtime is unavailable. Retry the approved action later."


class RuntimeRateLimited(DomainError):
    code = "RUNTIME_RATE_LIMITED"
    status_code = 429
    message = "Agent Runtime is rate limited. Retry the approved action later."

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__()


class RuntimeUnauthorized(DomainError):
    code = "RUNTIME_UNAUTHORIZED"
    status_code = 503
    message = "Agent Runtime rejected Relay credentials."


class RuntimeRequestTimeout(DomainError):
    code = "RUNTIME_REQUEST_TIMEOUT"
    status_code = 504
    message = "Agent Runtime did not respond before Relay's timeout. Execution state is unknown."


class RuntimeExecutionNotFound(DomainError):
    code = "RUNTIME_EXECUTION_NOT_FOUND"
    status_code = 404
    message = "Runtime execution not found."


class RuntimeExecutionFailed(DomainError):
    code = "RUNTIME_EXECUTION_FAILED"
    status_code = 502
    message = "Agent Runtime execution failed."


class RuntimeCancellationFailed(DomainError):
    code = "RUNTIME_CANCELLATION_FAILED"
    status_code = 502
    message = "Agent Runtime could not cancel the execution."


class RuntimeMalformedResponse(DomainError):
    code = "RUNTIME_MALFORMED_RESPONSE"
    status_code = 502
    message = "Agent Runtime returned an unexpected response."
