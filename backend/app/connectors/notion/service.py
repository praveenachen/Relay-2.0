from uuid import UUID

from sqlalchemy import select

from app.connectors.notion.client import NotionApiClient
from app.connectors.notion.errors import (
    NotionDestinationNotFound,
    NotionNotConnected,
    NotionTaskDatabaseNotFound,
)
from app.connectors.notion.schemas import NotionDestination, NotionTaskDatabase
from app.connectors.notion.tasks import NotionTaskPropertyMapping
from app.domain.enums import ConnectionStatus, Provider
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount, NotionDestinationRecord, NotionTaskDatabaseRecord
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


class NotionTaskSourceService:
    """Lists the user's Notion databases and persists which one, and which
    property mapping, PLAN reads academic tasks from. Separate from
    NotionDestinationService because task databases and LEARN's page
    destinations are different Notion object types with different selection
    state."""

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

    async def refresh(self, owner: UUID) -> list[NotionTaskDatabase]:
        connection = await self.connection(owner)
        databases = await (await self.client(connection)).search_databases()
        for database in databases:
            record_item = await self.session.scalar(
                select(NotionTaskDatabaseRecord).where(
                    NotionTaskDatabaseRecord.connection_id == connection.id,
                    NotionTaskDatabaseRecord.provider_database_id == database.id,
                )
            )
            if record_item is None:
                self.session.add(
                    NotionTaskDatabaseRecord(
                        user_id=owner,
                        connection_id=connection.id,
                        provider_database_id=database.id,
                        title=database.title,
                        property_mapping={},
                    )
                )
            else:
                record_item.title = database.title
        await self.session.commit()
        return await self.list(owner)

    async def list(self, owner: UUID) -> list[NotionTaskDatabase]:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(NotionTaskDatabaseRecord)
                .where(
                    NotionTaskDatabaseRecord.user_id == owner,
                    NotionTaskDatabaseRecord.connection_id == connection.id,
                )
                .order_by(NotionTaskDatabaseRecord.selected.desc(), NotionTaskDatabaseRecord.title)
            )
        ).all()
        return [
            NotionTaskDatabase(id=item.provider_database_id, title=item.title) for item in records
        ]

    async def select(
        self, owner: UUID, database_id: str, mapping: NotionTaskPropertyMapping
    ) -> NotionTaskDatabase:
        connection = await self.connection(owner)
        records = (
            await self.session.scalars(
                select(NotionTaskDatabaseRecord).where(
                    NotionTaskDatabaseRecord.user_id == owner,
                    NotionTaskDatabaseRecord.connection_id == connection.id,
                )
            )
        ).all()
        selected = None
        for item in records:
            item.selected = item.provider_database_id == database_id
            if item.selected:
                item.property_mapping = mapping.model_dump(mode="json")
                selected = item
        if selected is None:
            raise NotionTaskDatabaseNotFound()
        metadata = dict(connection.provider_metadata or {})
        metadata["default_task_database_id"] = selected.provider_database_id
        metadata["default_task_database_title"] = selected.title
        connection.provider_metadata = metadata
        record(
            self.session,
            owner,
            "NOTION_TASK_DATABASE_SELECTED",
            metadata={
                "connection_id": str(connection.id),
                "database_id": selected.provider_database_id,
            },
        )
        await self.session.commit()
        return NotionTaskDatabase(id=selected.provider_database_id, title=selected.title)

    async def default(self, owner: UUID) -> tuple[str, NotionTaskPropertyMapping] | None:
        """The database + mapping PLAN should use when a run's setup does
        not explicitly override them."""
        connection = await self.connection(owner)
        record_item = await self.session.scalar(
            select(NotionTaskDatabaseRecord).where(
                NotionTaskDatabaseRecord.user_id == owner,
                NotionTaskDatabaseRecord.connection_id == connection.id,
                NotionTaskDatabaseRecord.selected.is_(True),
            )
        )
        if record_item is None or not record_item.property_mapping:
            return None
        return record_item.provider_database_id, NotionTaskPropertyMapping.model_validate(
            record_item.property_mapping
        )
