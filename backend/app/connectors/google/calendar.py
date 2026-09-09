from datetime import datetime
from typing import Any

import httpx

from app.connectors.google.errors import (
    CalendarConflict,
    CalendarNotFound,
    CalendarRateLimited,
    CalendarRequestTimeout,
    CalendarUnavailable,
    GoogleAuthorizationFailed,
    GooglePermissionDenied,
)
from app.connectors.google.mapper import busy_interval_from_event
from app.connectors.google.schemas import (
    CalendarEventResult,
    CalendarListItem,
    CreateCalendarStudyBlockAction,
)
from app.scheduling.models import BusyInterval


def google_error(response: httpx.Response) -> Exception:
    if response.status_code == 401:
        return GoogleAuthorizationFailed()
    if response.status_code == 403:
        return GooglePermissionDenied()
    if response.status_code == 404:
        return CalendarNotFound()
    if response.status_code == 409:
        return CalendarConflict()
    if response.status_code == 429:
        return CalendarRateLimited()
    return CalendarUnavailable()


class GoogleCalendarApiClient:
    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://www.googleapis.com/calendar/v3",
        timeout: int = 20,
    ):
        self.access_token = access_token
        self.base_url = base_url
        self.timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json=json,
                    params=params,
                )
        except httpx.TimeoutException as error:
            raise CalendarRequestTimeout() from error
        except httpx.HTTPError as error:
            raise CalendarUnavailable() from error
        if response.status_code >= 400:
            raise google_error(response)
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def list_calendars(self) -> list[CalendarListItem]:
        data = await self.request("GET", "/users/me/calendarList")
        calendars: list[CalendarListItem] = []
        for item in data.get("items", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                calendars.append(
                    CalendarListItem(
                        id=item["id"],
                        summary=item.get("summary") or item["id"],
                        primary=bool(item.get("primary", False)),
                        time_zone=(
                            item.get("timeZone") if isinstance(item.get("timeZone"), str) else None
                        ),
                    )
                )
        return calendars

    async def busy_intervals(
        self, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[BusyInterval]:
        data = await self.request(
            "GET",
            f"/calendars/{calendar_id}/events",
            params={
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        return [
            busy_interval_from_event(item)
            for item in data.get("items", [])
            if isinstance(item, dict)
        ]

    async def create_event(
        self, action: CreateCalendarStudyBlockAction, idempotency_key: str
    ) -> CalendarEventResult:
        data = await self.request(
            "POST",
            f"/calendars/{action.calendar_id}/events",
            params={"conferenceDataVersion": 0},
            json={
                "summary": action.title,
                "description": f"{action.description or ''}\n\nRelay action: {idempotency_key}",
                "start": {"dateTime": action.start.isoformat()},
                "end": {"dateTime": action.end.isoformat()},
                "extendedProperties": {"private": {"relay_idempotency_key": idempotency_key}},
            },
        )
        event_id = data.get("id")
        if not isinstance(event_id, str):
            raise CalendarUnavailable()
        html_link = data.get("htmlLink") if isinstance(data.get("htmlLink"), str) else None
        return CalendarEventResult(
            external_id=event_id,
            external_url=html_link or "",
            html_link=html_link,
            title=action.title,
            calendar_id=action.calendar_id,
            start=action.start,
            end=action.end,
        )

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        await self.request("DELETE", f"/calendars/{calendar_id}/events/{event_id}")


class GoogleCalendarConnector:
    def __init__(self, client: GoogleCalendarApiClient):
        self.client = client

    async def list_calendars(self) -> list[CalendarListItem]:
        return await self.client.list_calendars()

    async def busy_intervals(
        self, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[BusyInterval]:
        return await self.client.busy_intervals(calendar_id, time_min, time_max)

    async def create_study_block(
        self, action: CreateCalendarStudyBlockAction, idempotency_key: str
    ) -> CalendarEventResult:
        return await self.client.create_event(action, idempotency_key)
