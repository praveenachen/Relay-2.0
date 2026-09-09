import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select

from app.connectors.google.errors import CalendarUnavailable, GoogleAuthorizationFailed
from app.connectors.google.schemas import GoogleOAuthToken, GoogleTokenInfo
from app.domain.enums import ConnectionStatus, Provider
from app.domain.errors import OAuthNotConfigured, UnauthorizedResourceAccess
from app.domain.ports import CredentialStore, OAuthCredentials
from app.models.entities import ConnectedAccount, OAuthState, now
from app.repositories.relay import RelayRepository
from app.schemas.domain import ConnectionRead
from app.services.audit import record
from app.services.connections import ConnectionService

CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
)


def hash_state(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class GoogleOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth",
        token_url: str = "https://oauth2.googleapis.com/token",
        userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo",
        timeout: int = 20,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
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
                    "response_type": "code",
                    "scope": " ".join((*CALENDAR_SCOPES, "openid", "email", "profile")),
                    "state": state,
                    "access_type": "offline",
                    "prompt": "consent",
                }
            )
        )

    async def exchange_code(self, code: str) -> GoogleOAuthToken:
        if not self.configured():
            raise OAuthNotConfigured()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                    },
                )
        except httpx.HTTPError as error:
            raise CalendarUnavailable() from error
        if response.status_code >= 400:
            raise GoogleAuthorizationFailed()
        return GoogleOAuthToken.model_validate(response.json())

    async def refresh(self, refresh_token: str) -> GoogleOAuthToken:
        if not self.configured():
            raise OAuthNotConfigured()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.HTTPError as error:
            raise CalendarUnavailable() from error
        if response.status_code >= 400:
            raise GoogleAuthorizationFailed()
        return GoogleOAuthToken.model_validate(response.json())

    async def userinfo(self, access_token: str) -> GoogleTokenInfo:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
                )
        except httpx.HTTPError as error:
            raise CalendarUnavailable() from error
        if response.status_code >= 400:
            raise GoogleAuthorizationFailed()
        return GoogleTokenInfo.model_validate(response.json())


class GoogleOAuthService:
    def __init__(
        self,
        repo: RelayRepository,
        oauth: GoogleOAuthClient,
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
                provider=Provider.GOOGLE,
                state_hash=hash_state(raw),
                expires_at=now() + timedelta(seconds=self.ttl_seconds),
            )
        )
        record(self.session, owner, "GOOGLE_AUTHORIZATION_STARTED", metadata={})
        await self.session.commit()
        return {"authorization_url": self.oauth.authorization_url(raw)}

    async def callback(
        self, owner: UUID, *, state: str | None, code: str | None, error: str | None
    ) -> ConnectionRead:
        if error or not state or not code:
            raise GoogleAuthorizationFailed()
        stored = await self.session.scalar(
            select(OAuthState).where(
                OAuthState.user_id == owner,
                OAuthState.provider == Provider.GOOGLE,
                OAuthState.state_hash == hash_state(state),
                OAuthState.consumed_at.is_(None),
            )
        )
        if stored is None or as_utc(stored.expires_at) < now():
            raise GoogleAuthorizationFailed()
        stored.consumed_at = now()
        token = await self.oauth.exchange_code(code)
        info = await self.oauth.userinfo(token.access_token)
        external_id = info.sub or info.email or "google-user"
        credentials = OAuthCredentials(
            external_account_id=external_id,
            display_name=info.email or info.name or "Google Calendar",
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=now() + timedelta(seconds=token.expires_in or 3600),
            scopes=tuple(scope for scope in token.scope.split() if scope) or CALENDAR_SCOPES,
        )
        service = ConnectionService(self.repo)
        existing = await self.repo.connections(owner, Provider.GOOGLE)
        match = next((item for item in existing if item.external_account_id == external_id), None)
        if match:
            connection = await service.replace(owner, match.id, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, match.id)
        else:
            connection = await service.create(owner, Provider.GOOGLE, credentials, self.store)
            stored_connection = await self.session.get(ConnectedAccount, connection.id)
        if stored_connection is None:
            raise UnauthorizedResourceAccess()
        stored_connection.status = ConnectionStatus.CONNECTED
        stored_connection.provider_metadata = {
            "email": info.email,
            "name": info.name,
            "picture": info.picture,
        }
        record(
            self.session,
            owner,
            "GOOGLE_CONNECTED",
            metadata={"connection_id": str(stored_connection.id)},
        )
        await self.session.commit()
        return ConnectionRead.model_validate(stored_connection)
