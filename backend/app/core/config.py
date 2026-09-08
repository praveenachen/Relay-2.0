from functools import lru_cache
from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: PostgresDsn = PostgresDsn("postgresql+psycopg://relay:relay@localhost:5432/relay")


@lru_cache
def get_settings() -> Settings:
    return Settings()
