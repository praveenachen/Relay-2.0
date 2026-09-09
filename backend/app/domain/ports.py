from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class CredentialStore(Protocol):
    def encrypt(self, value: str) -> str: ...
    def decrypt(self, value: str) -> str: ...


@dataclass(frozen=True)
class OAuthCredentials:
    external_account_id: str
    display_name: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: tuple[str, ...]


class OAuthProvider(Protocol):
    def get_authorization_url(self, state: str, redirect_uri: str) -> str: ...
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthCredentials: ...
    async def refresh_token(self, refresh_token: str) -> OAuthCredentials: ...
    async def revoke(self, access_token: str) -> None: ...
