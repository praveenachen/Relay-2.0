from app.domain.errors import DomainError


class PlanWorkflowInvalidState(DomainError):
    code = "PLAN_WORKFLOW_INVALID_STATE"
    status_code = 409
    message = "The PLAN workflow is not in a state that allows this operation."


class SchedulingInputInvalid(DomainError):
    code = "SCHEDULING_INPUT_INVALID"
    status_code = 422
    message = "The scheduling input is incomplete or invalid."


class ScheduleAdjustmentInvalid(DomainError):
    code = "SCHEDULE_ADJUSTMENT_INVALID"
    status_code = 422
    message = "That time block cannot be placed there."

    def __init__(self, message: str | None = None) -> None:
        if message:
            self.message = message
        super().__init__()


class CalendarDestinationRequired(DomainError):
    code = "CALENDAR_DESTINATION_REQUIRED"
    status_code = 409
    message = "Connect Google Calendar and select a calendar before adding these time blocks."
