import os

import pytest
from sqlalchemy import text

from app.db.session import get_engine


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RELAY_TEST_DATABASE") != "1", reason="PostgreSQL opt-in required")
def test_database_and_migration_baseline() -> None:
    engine = get_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0006_plan_integration"
            )
    finally:
        engine.dispose()
