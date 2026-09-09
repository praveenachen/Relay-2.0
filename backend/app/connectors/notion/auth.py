import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select

from app.connectors.notion.client import NOTION_VERSION
from app.connectors.notion.errors import NotionAuthorizationFailed, NotionUnavailable
from app.connectors.notion.schemas import NotionOAuthToken
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import OAuthNotConfigured, UnauthorizedResourceAccess
from app.domain.ports import CredentialStore, OAuthCredentials
from app.models.entities import ConnectedAccount, OAuthState, now
from app.repositories.relay import RelayRepository
from app.schemas.domain import ConnectionRead
from app.services.audit import record
from app.services.connections import ConnectionService


def hash_state(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class NotionOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        authorize_url: str = "https://api.notion.com/v1/oauth/authorize",
        token_url: str = "https://api.notion.com/v1/oauth/token",
        timeout: int = 20,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorize_url = authorize_url
        self.token_url = token_url
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
                    "owner": "user",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "response_type": "code",
                    "state": state,
                }
            )
        )

    async def exchange_code(self, code: str) -> NotionOAuthToken:
        if not self.configured():
            raise OAuthNotConfigured()
        credential = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.token_url,
                    headers={
                        "Authorization": f"Basic {credential}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Notion-Version": NOTION_VERSION,
                    },
                    json={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                )
        except httpx.HTTPError as error:
            raise NotionUnavailable() from error
        if response.status_code >= 400:
            raise NotionAuthorizationFailed()
        return NotionOAuthToken.model_validate(response.json())


class NotionOAuthService:
    def __init__(
        self,
        repo: RelayRepository,
        oauth: NotionOAuthClient,
        store: CredentialStore,
        *,
        ttl_seconds: int = 600,
    ):
        self.repo, self.session, self.oauth, self.store = repo, repo.session, oauth, store
        self.ttl_seconds = ttl_seconds

    async def start(self, owner: UUID) -> dict[str, str]:
        raw = secrets.token_urlsafe(32)
        state = OAuthState(
            user_id=owner,
            provider=Provider.NOTION,
            state_hash=hash_state(raw),
            expires_at=now() + timedelta(seconds=self.ttl_seconds),
        )
        self.session.add(state)
        record(self.session, owner, "NOTION_AUTHORIZATION_STARTED", metadata={})
        await self.session.commit()
        return {"authorization_url": self.oauth.authorization_url(raw)}

    async def callback(
        self,
        owner: UUID,
        *,
        state: str | None,
        code: str | None,
        error: str | None,
    ) -> ConnectionRead:
        if error:
            record(self.session, owner, "NOTION_CONNECTION_ERROR", metadata={"error": error})
            await self.session.commit()
            raise NotionAuthorizationFailed()
        if not state or not code:
            raise NotionAuthorizationFailed()
        stored = await self.session.scalar(
            select(OAuthState).where(
                OAuthState.user_id == owner,
                OAuthState.provider == Provider.NOTION,
                OAuthState.state_hash == hash_state(state),
                OAuthState.consumed_at.is_(None),
            )
        )
        if stored is None or as_utc(stored.expires_at) < now():
            raise NotionAuthorizationFailed()
        stored.consumed_at = now()
        token = await self.oauth.exchange_code(code)
        credentials = OAuthCredentials(
            external_account_id=token.workspace_id,
            display_name=token.workspace_name or "Notion workspace",
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=None,
            scopes=("read_content", "insert_content"),
        )
        service = ConnectionService(self.repo)
        existing = await self.repo.connections(owner, Provider.NOTION)
        match = next(
            (item for item in existing if item.external_account_id == token.workspace_id), None
        )
        metadata: dict[str, Any] = {
            "workspace_id": token.workspace_id,
            "workspace_name": token.workspace_name,
            "workspace_icon": token.workspace_icon,
            "bot_id": token.bot_id,
            "owner": token.owner,
        }
        if match:
            connection = await service.replace(owner, match.id, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, match.id)
        else:
            connection = await service.create(owner, Provider.NOTION, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, connection.id)
        if stored_connection is None:
            raise UnauthorizedResourceAccess()
        stored_connection.provider_metadata = metadata
        stored_connection.status = ConnectionStatus.CONNECTED
        record(
            self.session,
            owner,
            "NOTION_CONNECTED",
            metadata={
                "workspace_id": token.workspace_id,
                "connection_id": str(stored_connection.id),
            },
        )
        await self.session.commit()
        return ConnectionRead.model_validate(stored_connection)
