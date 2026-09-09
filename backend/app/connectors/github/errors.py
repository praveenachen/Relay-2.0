from app.domain.errors import DomainError


class GitHubNotConnected(DomainError):
    code = "GITHUB_NOT_CONNECTED"
    status_code = 409
    message = "GitHub is not connected."


class GitHubAuthorizationFailed(DomainError):
    code = "GITHUB_AUTHORIZATION_FAILED"
    status_code = 401
    message = "Your GitHub connection needs attention. Reconnect GitHub and try again."


class GitHubRepositoryNotFound(DomainError):
    code = "GITHUB_REPOSITORY_NOT_FOUND"
    status_code = 404
    message = "The configured GitHub repository could not be found."


class GitHubRepositoryAccessDenied(DomainError):
    code = "GITHUB_REPOSITORY_ACCESS_DENIED"
    status_code = 403
    message = "Relay does not have access to this GitHub repository."


class GitHubUserNotAssignable(DomainError):
    code = "GITHUB_USER_NOT_ASSIGNABLE"
    status_code = 422
    message = "This person cannot be assigned to issues in this repository."


class GitHubLabelNotFound(DomainError):
    code = "GITHUB_LABEL_NOT_FOUND"
    status_code = 422
    message = "This label does not exist in the repository."


class GitHubPullRequestNotFound(DomainError):
    code = "GITHUB_PULL_REQUEST_NOT_FOUND"
    status_code = 404
    message = "The referenced pull request could not be found."


class GitHubReviewerInvalid(DomainError):
    code = "GITHUB_REVIEWER_INVALID"
    status_code = 422
    message = "This reviewer cannot be requested on this pull request."


class GitHubValidationFailed(DomainError):
    code = "GITHUB_VALIDATION_FAILED"
    status_code = 422
    message = "GitHub rejected this request."


class GitHubRateLimited(DomainError):
    code = "GITHUB_RATE_LIMITED"
    status_code = 429
    message = "GitHub is rate limiting Relay. Try again shortly."

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__()


class GitHubUnavailable(DomainError):
    code = "GITHUB_UNAVAILABLE"
    status_code = 503
    message = "GitHub is temporarily unavailable. Try again later."


class GitHubRequestTimeout(DomainError):
    code = "GITHUB_REQUEST_TIMEOUT"
    status_code = 504
    message = "Relay could not confirm whether GitHub completed the request."
