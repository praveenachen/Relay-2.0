from uuid import UUID

import pytest
from conftest import login, register
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import (
    ConnectedAccountAlreadyExists,
    CredentialStorageUnavailable,
    OAuthNotConfigured,
)
from app.domain.ports import OAuthCredentials
from app.infrastructure.credentials import DeferredCredentialStore, FernetCredentialStore
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


def test_deferred_store_only_requires_configuration_when_used(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "token_encryption_key",
        type("Secret", (), {"get_secret_value": lambda self: ""})(),
    )
    store = DeferredCredentialStore()
    with pytest.raises(CredentialStorageUnavailable):
        store.decrypt("not-accessed-until-now")


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


async def test_oauth_fallback_is_honestly_unavailable(session_factory):
    # NOTION, GOOGLE, and GITHUB all have real OAuth implementations now
    # (see test_notion_integration.py, test_plan_connectors.py, and
    # test_github_connector.py). ConnectionService.authorize/callback is a
    # defensive fallback for a future provider added to the Provider enum
    # before its OAuth flow is wired into routes.py -- no longer reachable
    # through the API for any current provider, but still real code.
    async with session_factory() as session:
        service = ConnectionService(RelayRepository(session))
        with pytest.raises(OAuthNotConfigured):
            service.authorize(Provider.NOTION)
        with pytest.raises(OAuthNotConfigured):
            service.callback(Provider.NOTION)


async def test_connections_start_empty(client, account):
    assert (await client.get("/connections")).json() == []
