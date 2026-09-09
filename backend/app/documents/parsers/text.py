from app.documents.errors import DocumentEmpty, DocumentParseFailed
from app.documents.models import (
    DocumentMetadata,
    DocumentSection,
    ParsedDocument,
    UploadedDocument,
)


def decode(file: UploadedDocument) -> str:
    try:
        text = file.content.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as error:
        raise DocumentParseFailed() from error
    if "\x00" in text:
        raise DocumentParseFailed()
    if not text.strip():
        raise DocumentEmpty()
    return text


def document(
    file: UploadedDocument, sections: list[DocumentSection], parser: str, pages: int | None = None
) -> ParsedDocument:
    if not any(section.text.strip() for section in sections):
        raise DocumentEmpty()
    return ParsedDocument(
        title=next((section.heading for section in sections if section.heading), None),
        metadata=DocumentMetadata(
            filename=file.filename,
            page_count=pages,
            character_count=sum(len(section.text) for section in sections),
            parser=parser,
        ),
        sections=sections,
    )


class TextParser:
    async def parse(self, file: UploadedDocument) -> ParsedDocument:
        return document(file, [DocumentSection(id="s1", text=decode(file), order=0)], "text")
