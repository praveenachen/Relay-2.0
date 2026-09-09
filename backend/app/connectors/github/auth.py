import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select

from app.connectors.github.errors import GitHubAuthorizationFailed, GitHubUnavailable
from app.connectors.github.schemas import GitHubOAuthToken, GitHubUserInfo
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import OAuthNotConfigured, UnauthorizedResourceAccess
from app.domain.ports import CredentialStore, OAuthCredentials
from app.models.entities import ConnectedAccount, OAuthState, now
from app.repositories.relay import RelayRepository
from app.schemas.domain import ConnectionRead
from app.services.audit import record
from app.services.connections import ConnectionService

# Classic GitHub OAuth Apps have no fine-grained per-permission scopes --
# that granularity is exactly what a GitHub App would offer instead (see
# ADR-026). `repo` is the narrowest classic scope that still supports issue
# and pull-request work on private repositories, which student group
# projects commonly are. It is not requested alongside `delete_repo`,
# `admin:*`, or `workflow`.
GITHUB_SCOPES = ("repo",)


def hash_state(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class GitHubOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        authorize_url: str = "https://github.com/login/oauth/authorize",
        token_url: str = "https://github.com/login/oauth/access_token",
        api_base_url: str = "https://api.github.com",
        timeout: int = 20,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.api_base_url = api_base_url
        self.timeout = timeout

    def configured(self) -> bool:
        return all([self.client_id, self.client_secret, self.redirect_uri])

    def authorization_url(self, state: str) -> str:
        if not self.configured():
            raise OAuthNotConfigured()
        return (
            self.authorize_url
            + "?"
            + urlencode(
                {
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "scope": " ".join(GITHUB_SCOPES),
                    "state": state,
                    "allow_signup": "false",
                }
            )
        )

    async def exchange_code(self, code: str) -> GitHubOAuthToken:
        if not self.configured():
            raise OAuthNotConfigured()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.token_url,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                )
        except httpx.HTTPError as error:
            raise GitHubUnavailable() from error
        if response.status_code >= 400:
            raise GitHubAuthorizationFailed()
        data = response.json()
        # GitHub answers a bad code with HTTP 200 and an `error` field
        # instead of a non-2xx status.
        if not isinstance(data, dict) or "error" in data or "access_token" not in data:
            raise GitHubAuthorizationFailed()
        return GitHubOAuthToken.model_validate(data)

    async def userinfo(self, access_token: str) -> GitHubUserInfo:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base_url}/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
        except httpx.HTTPError as error:
            raise GitHubUnavailable() from error
        if response.status_code >= 400:
            raise GitHubAuthorizationFailed()
        return GitHubUserInfo.model_validate(response.json())


class GitHubOAuthService:
    def __init__(
        self,
        repo: RelayRepository,
        oauth: GitHubOAuthClient,
        store: CredentialStore,
        *,
        ttl_seconds: int = 600,
    ):
        self.repo = repo
        self.session = repo.session
        self.oauth = oauth
        self.store = store
        self.ttl_seconds = ttl_seconds

    async def start(self, owner: UUID) -> dict[str, str]:
        raw = secrets.token_urlsafe(32)
        self.session.add(
            OAuthState(
                user_id=owner,
                provider=Provider.GITHUB,
                state_hash=hash_state(raw),
                expires_at=now() + timedelta(seconds=self.ttl_seconds),
            )
        )
        record(self.session, owner, "GITHUB_AUTHORIZATION_STARTED", metadata={})
        await self.session.commit()
        return {"authorization_url": self.oauth.authorization_url(raw)}

    async def callback(
        self, owner: UUID, *, state: str | None, code: str | None, error: str | None
    ) -> ConnectionRead:
        if error or not state or not code:
            raise GitHubAuthorizationFailed()
        stored = await self.session.scalar(
            select(OAuthState).where(
                OAuthState.user_id == owner,
                OAuthState.provider == Provider.GITHUB,
                OAuthState.state_hash == hash_state(state),
                OAuthState.consumed_at.is_(None),
            )
        )
        if stored is None or as_utc(stored.expires_at) < now():
            raise GitHubAuthorizationFailed()
        stored.consumed_at = now()
        token = await self.oauth.exchange_code(code)
        info = await self.oauth.userinfo(token.access_token)
        external_id = str(info.id)
        credentials = OAuthCredentials(
            external_account_id=external_id,
            display_name=info.name or info.login,
            access_token=token.access_token,
            # Classic GitHub OAuth App tokens do not expire and have no
            # refresh token, unlike Google's -- see ADR-018.
            refresh_token=None,
            expires_at=None,
            scopes=tuple(scope for scope in token.scope.split(",") if scope) or GITHUB_SCOPES,
        )
        service = ConnectionService(self.repo)
        existing = await self.repo.connections(owner, Provider.GITHUB)
        match = next((item for item in existing if item.external_account_id == external_id), None)
        if match:
            connection = await service.replace(owner, match.id, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, match.id)
        else:
            connection = await service.create(owner, Provider.GITHUB, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, connection.id)
        if stored_connection is None:
            raise UnauthorizedResourceAccess()
        stored_connection.status = ConnectionStatus.CONNECTED
        stored_connection.provider_metadata = {"login": info.login, "name": info.name}
        record(
            self.session,
            owner,
            "GITHUB_CONNECTED",
            metadata={"connection_id": str(stored_connection.id)},
        )
        await self.session.commit()
        return ConnectionRead.model_validate(stored_connection)
