from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Construct lazily: importing the API must not connect to the database."""
    return create_engine(str(get_settings().database_url), pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """Caller owns transaction boundaries; close and roll back on exit."""
    with Session(get_engine()) as session:
        yield session
