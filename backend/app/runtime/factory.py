from collections.abc import Collection
from typing import Any, Literal

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

RuntimeCapability = Literal["notion", "calendar", "github"]


def runtime_client(
    repo: Repository,
    settings: Settings,
    *,
    capabilities: Collection[str],
) -> RuntimeClient:
    if settings.runtime_backend == "agent_runtime":
        api_key = settings.agent_runtime_api_key.get_secret_value()
        if not settings.agent_runtime_base_url or not api_key:
            raise RuntimeUnavailable()
        return AgentRuntimeHttpClient(
            settings.agent_runtime_base_url,
            api_key,
            timeout=settings.agent_runtime_timeout_seconds,
        )

    store = None
    notion_connector: Any = None
    calendar_connector: Any = None
    github_connector: Any = None

    if "notion" in capabilities:
        if settings.notion_publish_mode == "mock":
            notion_connector = MockNotionConnector()
        else:
            store = store or credential_store()
            notion_connector = DatabaseNotionConnector(
                repo.session,
                store,
                api_base_url=settings.notion_api_base_url,
                timeout=settings.notion_timeout_seconds,
            )
    if "calendar" in capabilities:
        store = store or credential_store()
        calendar_connector = DatabaseGoogleCalendarConnector(
            repo.session,
            store,
            api_base_url=settings.google_calendar_api_base_url,
            timeout=settings.google_timeout_seconds,
        )
    if "github" in capabilities:
        if settings.github_publish_mode == "mock":
            github_connector = MockGitHubConnector()
        else:
            store = store or credential_store()
            github_connector = DatabaseGitHubConnector(
                repo.session,
                store,
                api_base_url=settings.github_api_base_url,
                timeout=settings.github_timeout_seconds,
            )

    return LocalRuntimeClient(
        repo.session,
        notion_connector,
        calendar_connector=calendar_connector,
        github_connector=github_connector,
    )
