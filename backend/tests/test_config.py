import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_must_be_postgresql() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"database_url": "sqlite:///test.db"})
