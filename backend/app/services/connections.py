from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import (
    ConnectedAccountAlreadyExists,
    ConnectedAccountNotFound,
    OAuthNotConfigured,
)
from app.domain.ports import CredentialStore, OAuthCredentials
from app.models.entities import ConnectedAccount
from app.repositories.relay import RelayRepository
from app.schemas.domain import ConnectionRead
from app.services.audit import record


class ConnectionService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository
        self.session = repository.session

    async def create(
        self, owner: UUID, provider: Provider, credentials: OAuthCredentials, store: CredentialStore
    ) -> ConnectionRead:
        existing = await self.repo.connections(owner, provider)
        if any(c.external_account_id == credentials.external_account_id for c in existing):
            raise ConnectedAccountAlreadyExists()
        connection = ConnectedAccount(
            user_id=owner,
            provider=provider,
            external_account_id=credentials.external_account_id,
            display_name=credentials.display_name,
            status=ConnectionStatus.CONNECTED,
        )
        self.replace_credentials(connection, credentials, store)
        self.session.add(connection)
        try:
            await self.session.flush()
            record(
                self.session,
                owner,
                "CONNECTION_CREATED",
                metadata={"connection_id": str(connection.id), "provider": provider.value},
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise ConnectedAccountAlreadyExists() from None
        return ConnectionRead.model_validate(connection)

    @staticmethod
    def replace_credentials(
        connection: ConnectedAccount, credentials: OAuthCredentials, store: CredentialStore
    ) -> None:
        connection.access_token_encrypted = store.encrypt(credentials.access_token)
        connection.refresh_token_encrypted = (
            store.encrypt(credentials.refresh_token) if credentials.refresh_token else None
        )
        connection.token_expires_at = credentials.expires_at
        connection.scopes = list(credentials.scopes)

    async def replace(
        self,
        owner: UUID,
        connection_id: UUID,
        credentials: OAuthCredentials,
        store: CredentialStore,
    ) -> ConnectionRead:
        connection = await self.owned(owner, connection_id)
        if connection.external_account_id != credentials.external_account_id:
            raise ConnectedAccountNotFound()
        self.replace_credentials(connection, credentials, store)
        connection.status = ConnectionStatus.CONNECTED
        record(
            self.session,
            owner,
            "CONNECTION_CREDENTIALS_REPLACED",
            metadata={"connection_id": str(connection.id)},
        )
        await self.session.commit()
        return ConnectionRead.model_validate(connection)

    async def owned(self, owner: UUID, connection_id: UUID) -> ConnectedAccount:
        for connection in await self.repo.connections(owner, lock=True):
            if connection.id == connection_id:
                return connection
        raise ConnectedAccountNotFound()

    async def mark(
        self, owner: UUID, connection_id: UUID, status: ConnectionStatus
    ) -> ConnectionRead:
        connection = await self.owned(owner, connection_id)
        connection.status = status
        if status == ConnectionStatus.REVOKED:
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
        record(
            self.session,
            owner,
            "CONNECTION_STATUS_CHANGED",
            metadata={"connection_id": str(connection.id), "status": status.value},
        )
        await self.session.commit()
        return ConnectionRead.model_validate(connection)

    async def disconnect(self, owner: UUID, provider: Provider) -> None:
        connections = await self.repo.connections(owner, provider, lock=True)
        if not connections:
            raise ConnectedAccountNotFound()
        for connection in connections:
            if connection.status == ConnectionStatus.REVOKED:
                continue
            connection.status = ConnectionStatus.REVOKED
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None
            connection.token_expires_at = None
            record(
                self.session,
                owner,
                "CONNECTION_DISCONNECTED",
                metadata={"connection_id": str(connection.id), "provider": provider.value},
            )
        await self.session.commit()

    def authorize(self, provider: Provider) -> None:
        raise OAuthNotConfigured()

    def callback(self, provider: Provider) -> None:
        raise OAuthNotConfigured()
