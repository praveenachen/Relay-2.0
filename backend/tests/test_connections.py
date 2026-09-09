from uuid import UUID

import pytest
from conftest import login, register
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import ConnectedAccountAlreadyExists, CredentialStorageUnavailable
from app.domain.ports import OAuthCredentials
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import AuditEvent, ConnectedAccount
from app.repositories.relay import RelayRepository
from app.services.connections import ConnectionService


def test_authenticated_encryption():
    first, second = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    store = FernetCredentialStore([first])
    encrypted = store.encrypt("test-provider-token")
    assert encrypted != "test-provider-token"
    assert store.decrypt(encrypted) == "test-provider-token"
    assert FernetCredentialStore([second, first]).decrypt(encrypted) == "test-provider-token"
    with pytest.raises(CredentialStorageUnavailable):
        FernetCredentialStore([second]).decrypt(encrypted)
    with pytest.raises(CredentialStorageUnavailable):
        store.decrypt(encrypted[:-5] + "abcde")
    with pytest.raises(CredentialStorageUnavailable):
        FernetCredentialStore([])


async def test_connection_lifecycle_and_isolation(client, account, session_factory):
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    credentials = OAuthCredentials(
        "external-fixture",
        "Student account",
        "test-access-token",
        "test-refresh-token",
        None,
        ("read",),
    )
    async with session_factory() as session:
        service = ConnectionService(RelayRepository(session))
        created = await service.create(UUID(account["id"]), Provider.NOTION, credentials, store)
        with pytest.raises(ConnectedAccountAlreadyExists):
            await service.create(UUID(account["id"]), Provider.NOTION, credentials, store)
        await session.rollback()
        stored = await session.get(ConnectedAccount, created.id)
        assert store.decrypt(stored.access_token_encrypted) == "test-access-token"
        await service.mark(UUID(account["id"]), created.id, ConnectionStatus.EXPIRED)
        assert (
            await service.replace(UUID(account["id"]), created.id, credentials, store)
        ).status == ConnectionStatus.CONNECTED
    metadata = await client.get("/connections/NOTION")
    assert len(metadata.json()) == 1
    assert "encrypted" not in metadata.text and "test-access-token" not in metadata.text
    await client.post("/auth/logout")
    await register(client, "other@example.com")
    await login(client, "other@example.com")
    assert (await client.get("/connections/NOTION")).json() == []
    assert (await client.delete("/connections/NOTION")).status_code == 404
    await client.post("/auth/logout")
    await login(client)
    assert (await client.delete("/connections/NOTION")).status_code == 204
    assert (await client.delete("/connections/NOTION")).status_code == 204
    async with session_factory() as session:
        stored = await session.get(ConnectedAccount, created.id)
        assert stored.access_token_encrypted is None and stored.refresh_token_encrypted is None
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "CONNECTION_DISCONNECTED")
            )
        ).all()
        assert len(events) == 1


async def test_oauth_is_honestly_unavailable(client, account):
    # GOOGLE and NOTION have real OAuth implementations (see test_plan_connectors.py
    # and test_notion_integration.py); GITHUB (COLLABORATE, a later phase) does not yet.
    for path in ["/connections/GITHUB/authorize", "/connections/GITHUB/callback"]:
        response = await client.get(path)
        assert response.status_code == 501
        assert response.json()["code"] == "OAUTH_NOT_CONFIGURED"
    assert (await client.get("/connections")).json() == []
