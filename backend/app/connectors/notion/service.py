from uuid import UUID

from sqlalchemy import select

from app.connectors.notion.client import NotionApiClient
from app.connectors.notion.errors import NotionDestinationNotFound, NotionNotConnected
from app.connectors.notion.schemas import NotionDestination
from app.domain.enums import ConnectionStatus, Provider
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount, NotionDestinationRecord
from app.repositories.relay import RelayRepository
from app.services.audit import record


class NotionDestinationService:
    def __init__(
        self,
        repo: RelayRepository,
        store: CredentialStore,
        *,
        api_base_url: str = "https://api.notion.com",
        timeout: int = 20,
    ):
        self.repo, self.session, self.store = repo, repo.session, store
        self.api_base_url, self.timeout = api_base_url, timeout

    async def connection(self, owner: UUID) -> ConnectedAccount:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.NOTION, lock=True)
            if item.status == ConnectionStatus.CONNECTED and item.access_token_encrypted
        ]
        if not connections:
            raise NotionNotConnected()
        return connections[0]

    async def client(self, connection: ConnectedAccount) -> NotionApiClient:
        if connection.access_token_encrypted is None:
            raise NotionNotConnected()
        return NotionApiClient(
            self.store.decrypt(connection.access_token_encrypted),
            base_url=self.api_base_url,
            timeout=self.timeout,
        )

    async def refresh(self, owner: UUID) -> list[NotionDestination]:
        connection = await self.connection(owner)
        pages = await (await self.client(connection)).search_pages()
        for page in pages:
            record_item = await self.session.scalar(
                select(NotionDestinationRecord).where(
                    NotionDestinationRecord.connection_id == connection.id,
                    NotionDestinationRecord.provider_page_id == page.id,
                )
            )
            if record_item is None:
                self.session.add(
                    NotionDestinationRecord(
                        user_id=owner,
                        connection_id=connection.id,
                        provider_page_id=page.id,
                        title=page.title,
                        icon_url=page.icon_url,
                    )
                )
            else:
                record_item.title = page.title
                record_item.icon_url = page.icon_url
        await self.session.commit()
        return await self.list(owner)

    async def list(self, owner: UUID) -> list[NotionDestination]:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(NotionDestinationRecord)
                .where(
                    NotionDestinationRecord.user_id == owner,
                    NotionDestinationRecord.connection_id == connection.id,
                )
                .order_by(NotionDestinationRecord.selected.desc(), NotionDestinationRecord.title)
            )
        ).all()
        return [
            NotionDestination(id=item.provider_page_id, title=item.title, icon_url=item.icon_url)
            for item in records
        ]

    async def select(self, owner: UUID, destination_id: str) -> NotionDestination:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(NotionDestinationRecord).where(
                    NotionDestinationRecord.user_id == owner,
                    NotionDestinationRecord.connection_id == connection.id,
                )
            )
        ).all()
        selected = None
        for item in records:
            item.selected = item.provider_page_id == destination_id
            if item.selected:
                selected = item
        if selected is None:
            raise NotionDestinationNotFound()
        metadata = dict(connection.provider_metadata or {})
        metadata["default_destination_id"] = selected.provider_page_id
        metadata["default_destination_title"] = selected.title
        connection.provider_metadata = metadata
        record(
            self.session,
            owner,
            "NOTION_DESTINATION_SELECTED",
            metadata={
                "connection_id": str(connection.id),
                "destination_id": selected.provider_page_id,
            },
        )
        await self.session.commit()
        return NotionDestination(
            id=selected.provider_page_id,
            title=selected.title,
            icon_url=selected.icon_url,
        )
