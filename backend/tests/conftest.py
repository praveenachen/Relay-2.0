import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.auth.users import cookie_transport
from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    schema = "test_" + uuid4().hex
    live = os.getenv("RELAY_TEST_DATABASE") == "1"
    if live:
        url = str(get_settings().database_url).replace("+psycopg", "+asyncpg")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    def migrate(connection):
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    async with engine.begin() as connection:
        await connection.run_sync(migrate)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
    if live:
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
async def client(session_factory, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(cookie_transport, "cookie_secure", True)
    app = create_app()

    async def session_override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
        headers={"Origin": get_settings().frontend_origin},
    ) as client:
        yield client


async def register(client: httpx.AsyncClient, email: str = "student@example.com") -> dict:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "a sufficiently long test password", "name": "Student"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(client: httpx.AsyncClient, email: str = "student@example.com") -> httpx.Response:
    response = await client.post(
        "/auth/login", data={"username": email, "password": "a sufficiently long test password"}
    )
    assert response.status_code == 204, response.text
    return response


@pytest.fixture
async def account(client) -> dict:
    user = await register(client)
    await login(client)
    return user
