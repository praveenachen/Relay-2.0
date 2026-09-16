from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings
from app.domain.errors import CredentialStorageUnavailable
from app.domain.ports import CredentialStore


class FernetCredentialStore:
    def __init__(self, keys: list[str]):
        if not keys:
            raise CredentialStorageUnavailable()
        try:
            self.cipher = MultiFernet([Fernet(key.encode()) for key in keys])
        except (ValueError, TypeError):
            raise CredentialStorageUnavailable() from None

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            raise CredentialStorageUnavailable() from None


class DeferredCredentialStore:
    """Resolve encryption configuration only when credentials are accessed."""

    def encrypt(self, value: str) -> str:
        return credential_store().encrypt(value)

    def decrypt(self, value: str) -> str:
        return credential_store().decrypt(value)


def credential_store() -> CredentialStore:
    key = get_settings().token_encryption_key.get_secret_value()
    return FernetCredentialStore([part.strip() for part in key.split(",") if part.strip()])


def deferred_credential_store() -> CredentialStore:
    return DeferredCredentialStore()
