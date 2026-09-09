from uuid import UUID

from app.connectors.github.client import GitHubApiClient, GitHubConnector
from app.connectors.github.errors import GitHubNotConnected
from app.connectors.github.schemas import (
    GitHubCollaborator,
    GitHubLabel,
    GitHubPullRequest,
    GitHubRepository,
)
from app.domain.enums import ConnectionStatus, Provider
from app.domain.ports import CredentialStore
from app.models.entities import ConnectedAccount
from app.repositories.relay import RelayRepository


class GitHubService:
    """GitHub OAuth App tokens don't expire (ADR-018), so unlike
    GoogleCalendarService there is no refresh path here."""

    def __init__(
        self,
        repo: RelayRepository,
        store: CredentialStore,
        *,
        api_base_url: str = "https://api.github.com",
        timeout: int = 20,
    ):
        self.repo = repo
        self.session = repo.session
        self.store = store
        self.api_base_url = api_base_url
        self.timeout = timeout

    async def connection(self, owner: UUID) -> ConnectedAccount:
        connections = [
            item
            for item in await self.repo.connections(owner, Provider.GITHUB, lock=True)
            if item.status == ConnectionStatus.CONNECTED and item.access_token_encrypted
        ]
        if not connections:
            raise GitHubNotConnected()
        return connections[0]

    async def client(self, connection: ConnectedAccount) -> GitHubApiClient:
        if connection.access_token_encrypted is None:
            raise GitHubNotConnected()
        return GitHubApiClient(
            self.store.decrypt(connection.access_token_encrypted),
            base_url=self.api_base_url,
            timeout=self.timeout,
        )

    async def repositories(self, owner: UUID) -> list[GitHubRepository]:
        connection = await self.connection(owner)
        connector = GitHubConnector(await self.client(connection))
        return await connector.repositories()

    async def repository(self, owner: UUID, repo_owner: str, repo_name: str) -> GitHubRepository:
        connection = await self.connection(owner)
        connector = GitHubConnector(await self.client(connection))
        return await connector.repository(repo_owner, repo_name)

    async def collaborators(
        self, owner: UUID, repo_owner: str, repo_name: str
    ) -> list[GitHubCollaborator]:
        connection = await self.connection(owner)
        connector = GitHubConnector(await self.client(connection))
        return await connector.collaborators(repo_owner, repo_name)

    async def labels(self, owner: UUID, repo_owner: str, repo_name: str) -> list[GitHubLabel]:
        connection = await self.connection(owner)
        connector = GitHubConnector(await self.client(connection))
        return await connector.labels(repo_owner, repo_name)

    async def pull_request(
        self, owner: UUID, repo_owner: str, repo_name: str, number: int
    ) -> GitHubPullRequest:
        connection = await self.connection(owner)
        connector = GitHubConnector(await self.client(connection))
        return await connector.pull_request(repo_owner, repo_name, number)
