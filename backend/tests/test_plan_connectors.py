from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
import pytest
from cryptography.fernet import Fernet

from app.connectors.google.auth import GoogleOAuthClient, GoogleOAuthService
from app.connectors.google.calendar import GoogleCalendarApiClient
from app.connectors.google.errors import CalendarRateLimited, GoogleAuthorizationFailed
from app.connectors.google.schemas import GoogleOAuthToken, GoogleTokenInfo
from app.connectors.google.service import GoogleCalendarService
from app.connectors.notion.errors import NotionTaskDatabaseNotFound
from app.connectors.notion.schemas import NotionTaskDatabase
from app.connectors.notion.service import NotionTaskSourceService
from app.connectors.notion.tasks import NotionTaskMapper, NotionTaskPropertyMapping
from app.domain.enums import Provider
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import ConnectedAccount, GoogleCalendarRecord
from app.repositories.relay import RelayRepository

TZ = ZoneInfo("America/Toronto")


def notion_page(
    page_id: str,
    *,
    title: str = "Calculus Midterm",
    due: str | None = "2026-01-10T17:00:00-05:00",
    estimate: float | None = 3,
    status: str = "Todo",
    priority: int = 2,
):
    return {
        "id": page_id,
        "properties": {
            "Task Name": {"type": "title", "title": [{"plain_text": title}]},
            "Course": {"type": "rich_text", "rich_text": [{"plain_text": "MAT137"}]},
            "Due Date": {"type": "date", "date": {"start": due} if due else None},
            "Estimated Hours": {"type": "number", "number": estimate},
            "Status": {"type": "status", "status": {"name": status}},
            "Priority": {"type": "number", "number": priority},
        },
    }


def mapping() -> NotionTaskPropertyMapping:
    return NotionTaskPropertyMapping(
        title="Task Name",
        course="Course",
        deadline="Due Date",
        estimated_minutes="Estimated Hours",
        estimate_unit="hours",
        status="Status",
        priority="Priority",
    )


def test_notion_task_mapper_normalizes_valid_pages_and_excludes_done() -> None:
    result = NotionTaskMapper(mapping()).map_pages(
        [notion_page("task-1"), notion_page("task-2", status="Done")]
    )

    assert len(result.tasks) == 1
    task = result.tasks[0]
    assert task.id == "task-1"
    assert task.course == "MAT137"
    assert task.estimated_minutes == 180
    assert task.priority == 2
    assert not result.issues


def test_notion_task_mapper_reports_missing_deadline_and_estimate() -> None:
    result = NotionTaskMapper(mapping()).map_pages(
        [notion_page("task-1", due=None), notion_page("task-2", estimate=None)]
    )

    assert [issue.code for issue in result.issues] == [
        "TASK_DEADLINE_MISSING",
        "TASK_ESTIMATE_MISSING",
    ]
    assert not result.tasks


def test_google_oauth_url_uses_calendar_scopes_only() -> None:
    url = GoogleOAuthClient("client", "secret", "http://localhost/callback").authorization_url(
        "state-1"
    )

    assert "calendar.events" in url
    assert "calendar.readonly" in url
    assert "gmail" not in url.lower()


def test_google_oauth_token_accepts_google_testing_refresh_expiry_field() -> None:
    token = GoogleOAuthToken.model_validate(
        {
            "access_token": "google-access",
            "expires_in": 3600,
            "refresh_token": "google-refresh",
            "refresh_token_expires_in": 604799,
            "scope": "https://www.googleapis.com/auth/calendar.events",
            "token_type": "Bearer",
        }
    )

    assert token.access_token == "google-access"
    assert token.refresh_token == "google-refresh"


async def test_google_oauth_state_exchange_encrypts_tokens(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        service = GoogleOAuthService(
            RelayRepository(session),
            GoogleOAuthClient("client", "secret", "https://relay.test/connections/GOOGLE/callback"),
            store,
        )
        started = await service.start(UUID(account["id"]))
        state = started["authorization_url"].split("state=")[1].split("&")[0]

        async def exchange(code: str) -> GoogleOAuthToken:
            assert code == "code-1"
            return GoogleOAuthToken(
                access_token="google-access",
                refresh_token="google-refresh",
                expires_in=3600,
                scope="https://www.googleapis.com/auth/calendar.events",
            )

        async def userinfo(token: str) -> GoogleTokenInfo:
            assert token == "google-access"
            return GoogleTokenInfo(sub="google-user-1", email="student@example.com")

        service.oauth.exchange_code = exchange
        service.oauth.userinfo = userinfo
        connected = await service.callback(
            UUID(account["id"]), state=state, code="code-1", error=None
        )
        stored = await session.get(ConnectedAccount, connected.id)
        assert stored is not None
        assert stored.provider == Provider.GOOGLE
        assert stored.access_token_encrypted != "google-access"
        assert store.decrypt(stored.access_token_encrypted) == "google-access"
        assert store.decrypt(stored.refresh_token_encrypted) == "google-refresh"
        with pytest.raises(GoogleAuthorizationFailed):
            await service.callback(UUID(account["id"]), state=state, code="code-1", error=None)


async def test_google_calendar_http_mapping_and_errors() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path.endswith("/calendarList"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "primary",
                            "summary": "Primary",
                            "primary": True,
                            "timeZone": "America/Toronto",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/events") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "busy-1",
                            "start": {"dateTime": "2026-01-05T09:00:00-05:00"},
                            "end": {"dateTime": "2026-01-05T10:00:00-05:00"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/events") and request.method == "POST":
            body = request.read().decode()
            assert "Relay action: idem-1" in body
            return httpx.Response(
                200, json={"id": "event-1", "htmlLink": "https://calendar/event-1"}
            )
        return httpx.Response(429, json={"error": "rate"})

    transport = httpx.MockTransport(handler)

    class TestClient(GoogleCalendarApiClient):
        async def request(self, method, path, *, json=None, params=None):
            async with httpx.AsyncClient(
                transport=transport, base_url="https://www.googleapis.com/calendar/v3"
            ) as client:
                response = await client.request(method, path, json=json, params=params)
            if response.status_code >= 400:
                from app.connectors.google.calendar import google_error

                raise google_error(response)
            return response.json()

    client = TestClient("token")
    calendars = await client.list_calendars()
    assert calendars[0].id == "primary"
    busy = await client.busy_intervals(
        "primary",
        datetime(2026, 1, 5, 8, tzinfo=TZ),
        datetime(2026, 1, 5, 17, tzinfo=TZ),
    )
    assert busy[0].source_event_id == "busy-1"
    result = await client.create_event(
        __import__(
            "app.connectors.google.schemas", fromlist=["CreateCalendarStudyBlockAction"]
        ).CreateCalendarStudyBlockAction(
            task_id="task-1",
            title="Study Calculus",
            calendar_id="primary",
            start=datetime(2026, 1, 5, 11, tzinfo=TZ),
            end=datetime(2026, 1, 5, 12, tzinfo=TZ),
        ),
        "idem-1",
    )
    assert result.external_id == "event-1"
    with pytest.raises(CalendarRateLimited):
        await client.request("GET", "/other")


async def test_google_calendar_selection_persists(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        connection = ConnectedAccount(
            user_id=UUID(account["id"]),
            provider=Provider.GOOGLE,
            external_account_id="google-user-1",
            display_name="student@example.com",
            access_token_encrypted=store.encrypt("google-token"),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            provider_metadata={},
            status="CONNECTED",
        )
        session.add(connection)
        await session.commit()

        class Service(GoogleCalendarService):
            async def refresh(self, owner: UUID):
                self.session.add(
                    GoogleCalendarRecord(
                        user_id=owner,
                        connection_id=connection.id,
                        provider_calendar_id="school",
                        summary="School",
                        primary=False,
                        selected=False,
                    )
                )
                await self.session.commit()
                return await self.list(owner)

        service = Service(RelayRepository(session), store)
        await service.refresh(UUID(account["id"]))
        selected = await service.select(UUID(account["id"]), "school")
        assert selected.summary == "School"
        refreshed = await session.get(ConnectedAccount, connection.id)
        assert refreshed.provider_metadata["default_calendar_id"] == "school"


async def test_google_calendar_maps_403_and_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/forbidden"):
            return httpx.Response(403, json={"error": "forbidden"})
        raise httpx.TimeoutException("timed out", request=request)

    transport = httpx.MockTransport(handler)

    from app.connectors.google.calendar import google_error
    from app.connectors.google.errors import (
        CalendarRequestTimeout,
        CalendarUnavailable,
        GooglePermissionDenied,
    )

    class TestClient(GoogleCalendarApiClient):
        async def request(self, method, path, *, json=None, params=None):
            try:
                async with httpx.AsyncClient(
                    transport=transport, base_url="https://www.googleapis.com/calendar/v3"
                ) as client:
                    response = await client.request(method, path, json=json, params=params)
            except httpx.TimeoutException as error:
                raise CalendarRequestTimeout() from error
            except httpx.HTTPError as error:
                raise CalendarUnavailable() from error
            if response.status_code >= 400:
                raise google_error(response)
            return response.json()

    client = TestClient("token")
    with pytest.raises(GooglePermissionDenied):
        await client.request("GET", "/forbidden")
    with pytest.raises(CalendarRequestTimeout):
        await client.request("GET", "/anything")


def test_all_day_busy_event_is_treated_as_utc_midnight() -> None:
    from app.connectors.google.mapper import busy_interval_from_event

    interval = busy_interval_from_event(
        {
            "id": "all-day-1",
            "start": {"date": "2026-01-05"},
            "end": {"date": "2026-01-06"},
        }
    )
    assert interval.start.isoformat() == "2026-01-05T00:00:00+00:00"
    assert interval.end.isoformat() == "2026-01-06T00:00:00+00:00"
    assert interval.source_event_id == "all-day-1"


async def test_google_token_refresh_updates_stored_credentials(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        connection = ConnectedAccount(
            user_id=UUID(account["id"]),
            provider=Provider.GOOGLE,
            external_account_id="google-user-1",
            display_name="student@example.com",
            access_token_encrypted=store.encrypt("stale-access"),
            refresh_token_encrypted=store.encrypt("refresh-1"),
            token_expires_at=datetime(2020, 1, 1),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            provider_metadata={},
            status="CONNECTED",
        )
        session.add(connection)
        await session.commit()

        oauth = GoogleOAuthClient("client", "secret", "https://relay.test/callback")

        async def refresh(refresh_token: str) -> GoogleOAuthToken:
            assert refresh_token == "refresh-1"
            return GoogleOAuthToken(access_token="fresh-access", expires_in=3600)

        oauth.refresh = refresh
        service = GoogleCalendarService(RelayRepository(session), store, oauth=oauth)
        refreshed = await service.connection(UUID(account["id"]))
        assert store.decrypt(refreshed.access_token_encrypted) == "fresh-access"
        assert refreshed.token_expires_at is not None


async def test_google_token_refresh_without_refresh_token_marks_expired(
    account, session_factory
) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        connection = ConnectedAccount(
            user_id=UUID(account["id"]),
            provider=Provider.GOOGLE,
            external_account_id="google-user-1",
            display_name="student@example.com",
            access_token_encrypted=store.encrypt("stale-access"),
            refresh_token_encrypted=None,
            token_expires_at=datetime(2020, 1, 1),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            provider_metadata={},
            status="CONNECTED",
        )
        session.add(connection)
        await session.commit()

        service = GoogleCalendarService(RelayRepository(session), store)
        with pytest.raises(GoogleAuthorizationFailed):
            await service.connection(UUID(account["id"]))
        refreshed = await session.get(ConnectedAccount, connection.id)
        assert refreshed.status == "EXPIRED"


async def test_notion_task_database_discovery_select_and_default(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        connection = ConnectedAccount(
            user_id=UUID(account["id"]),
            provider=Provider.NOTION,
            external_account_id="workspace-1",
            display_name="Student Workspace",
            access_token_encrypted=store.encrypt("notion-token"),
            scopes=["read_content", "insert_content"],
            provider_metadata={"workspace_id": "workspace-1"},
            status="CONNECTED",
        )
        session.add(connection)
        await session.commit()

        class FakeClient:
            async def search_databases(self):
                return [
                    NotionTaskDatabase(id="db-1", title="Assignments"),
                    NotionTaskDatabase(id="db-2", title="Archive"),
                ]

        class Service(NotionTaskSourceService):
            async def client(self, connection):
                return FakeClient()

        service = Service(RelayRepository(session), store)
        owner = UUID(account["id"])
        refreshed = await service.refresh(owner)
        assert {item.title for item in refreshed} == {"Assignments", "Archive"}

        with pytest.raises(NotionTaskDatabaseNotFound):
            await service.select(owner, "missing", mapping())

        selected = await service.select(owner, "db-1", mapping())
        assert selected.title == "Assignments"

        default = await service.default(owner)
        assert default is not None
        database_id, saved_mapping = default
        assert database_id == "db-1"
        assert saved_mapping.title == mapping().title
