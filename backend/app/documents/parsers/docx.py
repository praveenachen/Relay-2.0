import asyncio
from io import BytesIO
from zipfile import ZipFile

from docx import Document

from app.documents.errors import DocumentTooLarge
from app.documents.models import DocumentSection, ParsedDocument, UploadedDocument
from app.documents.parsers.text import document


class DocxParser:
    def __init__(self, max_expanded_bytes: int):
        self.max_expanded_bytes = max_expanded_bytes

    async def parse(self, file: UploadedDocument) -> ParsedDocument:
        return await asyncio.to_thread(self._parse, file)

    def _parse(self, file: UploadedDocument) -> ParsedDocument:
        with ZipFile(BytesIO(file.content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > self.max_expanded_bytes:
                raise DocumentTooLarge()
        doc = Document(BytesIO(file.content))
        sections: list[DocumentSection] = []
        current = DocumentSection(id="s1", text="", order=0)
        for paragraph in doc.paragraphs:
            style = paragraph.style.name if paragraph.style else ""
            if style.startswith("Heading") and paragraph.text.strip():
                if current.text or current.heading:
                    sections.append(current)
                suffix = style.removeprefix("Heading").strip()
                current = DocumentSection(
                    id=f"s{len(sections) + 1}",
                    heading=paragraph.text,
                    level=int(suffix) if suffix.isdigit() else 1,
                    text="",
                    order=len(sections),
                )
            else:
                prefix = "- " if "List" in style else ""
                current.text += prefix + paragraph.text + "\n\n"
        if current.text or current.heading:
            sections.append(current)
        return document(file, sections, "python-docx")
