from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)
    max_document_characters: int = Field(default=500000, ge=1000)
    document_storage_path: Path = ROOT / ".data" / "documents"
    max_direct_summary_tokens: int = Field(default=6000, ge=256)
    max_section_summary_tokens: int = Field(default=3000, ge=128)
    language_model_provider: Literal["fake", "openai"] = "fake"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    model_timeout_seconds: int = Field(default=60, ge=1, le=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()
