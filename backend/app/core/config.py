from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: PostgresDsn = PostgresDsn("postgresql+psycopg://relay:relay@localhost:5432/relay")

    token_encryption_key: SecretStr = SecretStr("")
    cookie_secure: bool = True
    frontend_origin: str = "http://localhost:3000"
    session_lifetime_seconds: int = Field(default=86400, ge=300, le=2592000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
