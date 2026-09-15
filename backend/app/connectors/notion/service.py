from uuid import UUID

from sqlalchemy import delete, select

from app.connectors.notion.client import NotionApiClient
from app.connectors.notion.errors import NotionDestinationNotFound, NotionNotConnected
from app.connectors.notion.schemas import NotionDestination
from app.domain.enums import ActionProvider, ConnectionStatus, Provider
from app.domain.ports import CredentialStore
from app.models.entities import (
    ConnectedAccount,
    ExternalArtifact,
    NotionDestinationRecord,
    WorkflowRun,
)
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

    async def list_databases(self, owner: UUID) -> list[NotionDestination]:
        """Existing databases the connection can see, for Collaborate's
        project setup to pick which one to sync action items into. Unlike
        pages, these are never persisted/selected as a workflow "default" --
        just a live list fetched on demand. Defined before `list` below so
        this return-type annotation still resolves to the builtin list."""
        connection = await self.connection(owner)
        databases = await (await self.client(connection)).search_databases()
        seen_titles: set[str] = set()
        unique: list[NotionDestination] = []
        for database in databases:
            key = " ".join(database.title.casefold().split())
            if key in seen_titles:
                continue
            seen_titles.add(key)
            unique.append(database)
        return unique

    async def refresh(self, owner: UUID) -> list[NotionDestination]:
        connection = await self.connection(owner)
        pages = await (await self.client(connection)).search_pages()
        generated_ids = {
            value.replace("-", "").lower()
            for value in await self.session.scalars(
                select(ExternalArtifact.external_id)
                .join(WorkflowRun, ExternalArtifact.workflow_run_id == WorkflowRun.id)
                .where(
                    WorkflowRun.user_id == owner, ExternalArtifact.provider == ActionProvider.NOTION
                )
            )
        }
        pages = [page for page in pages if page.id.replace("-", "").lower() not in generated_ids]
        page_ids = [page.id for page in pages]
        await self.session.execute(
            delete(NotionDestinationRecord).where(
                NotionDestinationRecord.user_id == owner,
                NotionDestinationRecord.connection_id == connection.id,
                NotionDestinationRecord.provider_page_id.not_in(page_ids),
            )
        )
        metadata = dict(connection.provider_metadata or {})
        if metadata.get("default_destination_id") not in page_ids:
            metadata.pop("default_destination_id", None)
            metadata.pop("default_destination_title", None)
            connection.provider_metadata = metadata
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
        return await self._cached_list(owner)

    async def _cached_list(self, owner: UUID) -> list[NotionDestination]:
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

    async def list(self, owner: UUID) -> list[NotionDestination]:
        return await self.refresh(owner)

    async def select(self, owner: UUID, destination_id: str) -> NotionDestination:
        await self.refresh(owner)
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
