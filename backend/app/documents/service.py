import re
from pathlib import PurePosixPath

from app.documents.base import DocumentParser
from app.documents.errors import (
    DocumentEmpty,
    DocumentParseFailed,
    DocumentTooLarge,
    UnsupportedDocumentType,
)
from app.documents.models import ParsedDocument, UploadedDocument
from app.documents.parsers.docx import DocxParser
from app.documents.parsers.markdown import MarkdownParser
from app.documents.parsers.pdf import PdfParser
from app.documents.parsers.text import TextParser
from app.domain.errors import DomainError

SUPPORTED_DOCUMENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown"},
    ".markdown": {"text/markdown", "text/plain", "text/x-markdown"},
    ".txt": {"text/plain"},
}


class DocumentService:
    def __init__(self, max_bytes: int, max_characters: int):
        self.max_bytes = max_bytes
        self.max_characters = max_characters
        self.parsers: dict[str, DocumentParser] = {
            ".pdf": PdfParser(),
            ".docx": DocxParser(max_bytes * 10),
            ".md": MarkdownParser(),
            ".markdown": MarkdownParser(),
            ".txt": TextParser(),
        }

    def validate(self, filename: str, content_type: str, content: bytes) -> UploadedDocument:
        name = PurePosixPath(filename.replace("\\", "/")).name
        name = re.sub(r"[^\w. ()-]", "_", name)[:255]
        extension = PurePosixPath(name).suffix.lower()
        allowed = SUPPORTED_DOCUMENT_TYPES.get(extension)
        mime = content_type.split(";")[0].lower()
        if allowed is None or mime not in allowed | {"", "application/octet-stream"}:
            raise UnsupportedDocumentType()
        if not content:
            raise DocumentEmpty()
        if len(content) > self.max_bytes:
            raise DocumentTooLarge()
        if extension == ".pdf" and not content.startswith(b"%PDF-"):
            raise UnsupportedDocumentType()
        if extension == ".docx" and not content.startswith(b"PK\x03\x04"):
            raise UnsupportedDocumentType()
        if extension in {".md", ".markdown", ".txt"}:
            if content.startswith((b"MZ", b"\x7fELF")) or b"\x00" in content:
                raise UnsupportedDocumentType()
        canonical = sorted(allowed)[0] if mime in {"", "application/octet-stream"} else mime
        return UploadedDocument(name, canonical, content)

    async def parse(self, file: UploadedDocument) -> ParsedDocument:
        try:
            parsed = await self.parsers[PurePosixPath(file.filename).suffix.lower()].parse(file)
            if parsed.metadata.character_count > self.max_characters:
                raise DocumentTooLarge()
            return parsed
        except DomainError:
            raise
        except Exception as error:
            raise DocumentParseFailed() from error
