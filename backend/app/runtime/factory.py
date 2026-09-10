from app.api.dependencies import Repository
from app.connectors.github.mock import MockGitHubConnector
from app.connectors.notion import MockNotionConnector
from app.core.config import Settings
from app.infrastructure.credentials import credential_store
from app.runtime.client import RuntimeClient
from app.runtime.errors import RuntimeUnavailable
from app.runtime.http import AgentRuntimeHttpClient
from app.runtime.local import (
    DatabaseGitHubConnector,
    DatabaseGoogleCalendarConnector,
    DatabaseNotionConnector,
    LocalRuntimeClient,
)


def runtime_client(repo: Repository, settings: Settings) -> RuntimeClient:
    if settings.runtime_backend == "agent_runtime":
        api_key = settings.agent_runtime_api_key.get_secret_value()
        if not settings.agent_runtime_base_url or not api_key:
            raise RuntimeUnavailable()
        return AgentRuntimeHttpClient(
            settings.agent_runtime_base_url,
            api_key,
            timeout=settings.agent_runtime_timeout_seconds,
        )
    notion_connector = (
        MockNotionConnector()
        if settings.notion_publish_mode == "mock"
        else DatabaseNotionConnector(
            repo.session,
            credential_store(),
            api_base_url=settings.notion_api_base_url,
            timeout=settings.notion_timeout_seconds,
        )
    )
    github_connector = (
        MockGitHubConnector()
        if settings.github_publish_mode == "mock"
        else DatabaseGitHubConnector(
            repo.session,
            credential_store(),
            api_base_url=settings.github_api_base_url,
            timeout=settings.github_timeout_seconds,
        )
    )
    return LocalRuntimeClient(
        repo.session,
        notion_connector,
        calendar_connector=DatabaseGoogleCalendarConnector(
            repo.session,
            credential_store(),
            api_base_url=settings.google_calendar_api_base_url,
            timeout=settings.google_timeout_seconds,
        ),
        github_connector=github_connector,
    )
