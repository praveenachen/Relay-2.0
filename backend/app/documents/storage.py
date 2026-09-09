import asyncio
import re
from pathlib import Path
from uuid import uuid4

from app.documents.errors import DocumentStorageUnavailable


class LocalFileStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise DocumentStorageUnavailable()
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise DocumentStorageUnavailable()
        return path

    async def save(self, content: bytes) -> str:
        key = uuid4().hex
        try:
            await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self.path(key).write_bytes, content)
        except OSError as error:
            raise DocumentStorageUnavailable() from error
        return key

    async def read(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self.path(key).read_bytes)
        except OSError as error:
            raise DocumentStorageUnavailable() from error

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self.path(key).unlink, missing_ok=True)
        except OSError as error:
            raise DocumentStorageUnavailable() from error
