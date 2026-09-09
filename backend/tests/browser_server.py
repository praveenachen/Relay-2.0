"""Ephemeral SQLite API for browser tests. Never used by application startup."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["COOKIE_SECURE"] = "false"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3010"

import uvicorn  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()


@asynccontextmanager
async def lifespan(application):
    with TemporaryDirectory(prefix="relay-browser-") as directory:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory) / 'browser.db'}")

        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        def migrate(connection):
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

        async with engine.begin() as connection:
            await connection.run_sync(migrate)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def sessions():
            async with factory() as session:
                yield session

        application.dependency_overrides[get_session] = sessions
        yield
        await engine.dispose()


app.router.lifespan_context = lifespan
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010)
