from app.domain.errors import DomainError


class SummaryGenerationFailed(DomainError):
    code = "SUMMARY_GENERATION_FAILED"
    status_code = 502
    message = "Study notes could not be generated. Start a new run to try again."


class MalformedModelOutput(SummaryGenerationFailed):
    code = "MALFORMED_MODEL_OUTPUT"
    message = "The generated notes failed validation. Nothing was proposed or published."


class ModelUnavailable(SummaryGenerationFailed):
    code = "MODEL_UNAVAILABLE"
    status_code = 503
    message = "The model provider is unavailable. Check configuration or try a new run later."


class ModelTimeout(SummaryGenerationFailed):
    code = "MODEL_TIMEOUT"
    status_code = 504
    message = "The model timed out. Start a new run to try again."


class ModelRateLimited(SummaryGenerationFailed):
    code = "MODEL_RATE_LIMITED"
    status_code = 429
    message = "The model provider is busy. Start a new run later."


class LearnWorkflowInvalidState(DomainError):
    code = "LEARN_WORKFLOW_INVALID_STATE"
    status_code = 409
    message = "This operation is unavailable at the current workflow stage. Refresh the run."


class LearnSummaryNotFound(DomainError):
    code = "LEARN_SUMMARY_NOT_FOUND"
    status_code = 404
    message = "No study notes exist for this run."


class NotionDestinationMissing(DomainError):
    code = "NOTION_DESTINATION_MISSING"
    status_code = 422
    message = "Choose the Mock Notion / University Notes destination."
