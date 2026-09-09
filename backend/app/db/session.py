from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Synchronous engine for migration and database diagnostics only."""
    return create_engine(str(get_settings().database_url), pool_pre_ping=True)


@lru_cache
def get_async_engine() -> AsyncEngine:
    url = str(get_settings().database_url).replace("postgresql+psycopg://", "postgresql+asyncpg://")
    return create_async_engine(url, pool_pre_ping=True)


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(get_async_engine(), expire_on_commit=False)
    async with factory() as session:
        yield session
