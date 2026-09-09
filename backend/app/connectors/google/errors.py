from app.domain.errors import DomainError


class GoogleNotConnected(DomainError):
    code = "GOOGLE_NOT_CONNECTED"
    message = "Google Calendar is not connected."


class GoogleAuthorizationFailed(DomainError):
    code = "GOOGLE_AUTHORIZATION_FAILED"
    message = "Google authorization failed."


class GooglePermissionDenied(DomainError):
    code = "GOOGLE_PERMISSION_DENIED"
    message = "Google Calendar permission was denied."


class CalendarNotFound(DomainError):
    code = "CALENDAR_NOT_FOUND"
    message = "The selected Google Calendar could not be found."


class CalendarUnavailable(DomainError):
    code = "CALENDAR_UNAVAILABLE"
    message = "Google Calendar is unavailable."


class CalendarRateLimited(DomainError):
    code = "CALENDAR_RATE_LIMITED"
    message = "Google Calendar rate limit was reached."


class CalendarConflict(DomainError):
    code = "CALENDAR_CONFLICT"
    message = "Google Calendar rejected the study block because of a conflict."


class CalendarRequestTimeout(DomainError):
    code = "CALENDAR_REQUEST_TIMEOUT"
    message = "Google Calendar request timed out."
