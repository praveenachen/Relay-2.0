import asyncio

import pymupdf

from app.documents.errors import DocumentHasNoExtractableText
from app.documents.models import DocumentSection, ParsedDocument, UploadedDocument
from app.documents.parsers.text import document


class PdfParser:
    async def parse(self, file: UploadedDocument) -> ParsedDocument:
        return await asyncio.to_thread(self._parse, file)

    def _parse(self, file: UploadedDocument) -> ParsedDocument:
        with pymupdf.open(stream=file.content, filetype="pdf") as pdf:  # type: ignore[no-untyped-call]
            sections: list[DocumentSection] = []
            for page in pdf:
                text = page.get_text("text", sort=True).strip()
                if text:
                    sections.append(
                        DocumentSection(
                            id=f"s{len(sections) + 1}",
                            text=text,
                            order=len(sections),
                            source_page_start=page.number + 1,
                            source_page_end=page.number + 1,
                        )
                    )
            if not sections:
                raise DocumentHasNoExtractableText()
            return document(file, sections, "pymupdf", len(pdf))
