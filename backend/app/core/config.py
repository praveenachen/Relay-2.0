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
    notion_client_id: str = ""
    notion_client_secret: SecretStr = SecretStr("")
    notion_redirect_uri: str = "http://localhost:8000/connections/NOTION/callback"
    notion_api_base_url: str = "https://api.notion.com"
    notion_oauth_authorize_url: str = "https://api.notion.com/v1/oauth/authorize"
    notion_oauth_token_url: str = "https://api.notion.com/v1/oauth/token"
    notion_timeout_seconds: int = Field(default=20, ge=1, le=120)
    notion_publish_mode: Literal["mock", "real"] = "mock"
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/connections/GOOGLE/callback"
    google_calendar_api_base_url: str = "https://www.googleapis.com/calendar/v3"
    google_oauth_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_oauth_token_url: str = "https://oauth2.googleapis.com/token"
    google_userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"
    google_timeout_seconds: int = Field(default=20, ge=1, le=120)


@lru_cache
def get_settings() -> Settings:
    return Settings()
