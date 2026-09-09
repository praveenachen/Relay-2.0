from datetime import UTC
from uuid import UUID

from sqlalchemy import select

from app.connectors.google.calendar import GoogleCalendarApiClient
from app.connectors.google.errors import GoogleAuthorizationFailed, GoogleNotConnected
from app.connectors.google.schemas import CalendarListItem
from app.domain.enums import ConnectionStatus, Provider
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount, GoogleCalendarRecord, now
from app.repositories.relay import RelayRepository
from app.services.audit import record


class GoogleCalendarService:
    def __init__(
        self,
        repo: RelayRepository,
        store: CredentialStore,
        *,
        api_base_url: str = "https://www.googleapis.com/calendar/v3",
        timeout: int = 20,
    ):
        self.repo = repo
        self.session = repo.session
        self.store = store
        self.api_base_url = api_base_url
        self.timeout = timeout

    async def connection(self, owner: UUID) -> ConnectedAccount:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.GOOGLE, lock=True)
            if item.status == ConnectionStatus.CONNECTED and item.access_token_encrypted
        ]
        if not connections:
            raise GoogleNotConnected()
        connection = connections[0]
        if connection.token_expires_at and connection.token_expires_at.replace(tzinfo=UTC) <= now():
            raise GoogleAuthorizationFailed()
        return connection

    async def client(self, connection: ConnectedAccount) -> GoogleCalendarApiClient:
        if connection.access_token_encrypted is None:
            raise GoogleNotConnected()
        return GoogleCalendarApiClient(
            self.store.decrypt(connection.access_token_encrypted),
            base_url=self.api_base_url,
            timeout=self.timeout,
        )

    async def refresh(self, owner: UUID) -> list[CalendarListItem]:
        connection = await self.connection(owner)
        calendars = await (await self.client(connection)).list_calendars()
        for calendar in calendars:
            record_item = await self.session.scalar(
                select(GoogleCalendarRecord).where(
                    GoogleCalendarRecord.connection_id == connection.id,
                    GoogleCalendarRecord.provider_calendar_id == calendar.id,
                )
            )
            if record_item is None:
                self.session.add(
                    GoogleCalendarRecord(
                        user_id=owner,
                        connection_id=connection.id,
                        provider_calendar_id=calendar.id,
                        summary=calendar.summary,
                        time_zone=calendar.time_zone,
                        primary=calendar.primary,
                        selected=calendar.primary,
                    )
                )
            else:
                record_item.summary = calendar.summary
                record_item.time_zone = calendar.time_zone
                record_item.primary = calendar.primary
        await self.session.commit()
        return await self.list(owner)

    async def list(self, owner: UUID) -> list[CalendarListItem]:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(GoogleCalendarRecord)
                .where(
                    GoogleCalendarRecord.user_id == owner,
                    GoogleCalendarRecord.connection_id == connection.id,
                )
                .order_by(
                    GoogleCalendarRecord.selected.desc(),
                    GoogleCalendarRecord.primary.desc(),
                    GoogleCalendarRecord.summary,
                )
            )
        ).all()
        return [
            CalendarListItem(
                id=item.provider_calendar_id,
                summary=item.summary,
                primary=item.primary,
                time_zone=item.time_zone,
            )
            for item in records
        ]

    async def select(self, owner: UUID, calendar_id: str) -> CalendarListItem:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(GoogleCalendarRecord).where(
                    GoogleCalendarRecord.user_id == owner,
                    GoogleCalendarRecord.connection_id == connection.id,
                )
            )
        ).all()
        selected = None
        for item in records:
            item.selected = item.provider_calendar_id == calendar_id
            if item.selected:
                selected = item
        if selected is None:
            raise GoogleNotConnected()
        metadata = dict(connection.provider_metadata or {})
        metadata["default_calendar_id"] = selected.provider_calendar_id
        metadata["default_calendar_summary"] = selected.summary
        connection.provider_metadata = metadata
        record(
            self.session,
            owner,
            "GOOGLE_CALENDAR_SELECTED",
            metadata={"calendar_id": selected.provider_calendar_id},
        )
        await self.session.commit()
        return CalendarListItem(
            id=selected.provider_calendar_id,
            summary=selected.summary,
            primary=selected.primary,
            time_zone=selected.time_zone,
        )
