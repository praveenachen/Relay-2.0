from datetime import datetime
from typing import Any

from pydantic import Field

from app.workflows.lecture_notes.schemas import StrictModel


class GoogleOAuthToken(StrictModel):
    access_token: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str = ""
    token_type: str = "Bearer"
    id_token: str | None = None


class GoogleTokenInfo(StrictModel):
    sub: str | None = None
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class CalendarListItem(StrictModel):
    id: str
    summary: str
    primary: bool = False
    time_zone: str | None = None


class CalendarEventResult(StrictModel):
    external_id: str
    external_url: str = ""
    title: str
    calendar_id: str
    start: datetime
    end: datetime
    html_link: str | None = None


class CreateCalendarStudyBlockAction(StrictModel):
    task_id: str
    title: str = Field(min_length=1, max_length=255)
    start: datetime
    end: datetime
    description: str | None = None
    calendar_id: str
    connection_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
