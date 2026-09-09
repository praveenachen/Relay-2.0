import re

from app.documents.models import DocumentSection, ParsedDocument, UploadedDocument
from app.documents.parsers.text import decode, document


class MarkdownParser:
    async def parse(self, file: UploadedDocument) -> ParsedDocument:
        sections: list[DocumentSection] = []
        heading: str | None = None
        level: int | None = None
        lines: list[str] = []
        fenced = False

        def flush() -> None:
            if lines or heading:
                sections.append(
                    DocumentSection(
                        id=f"s{len(sections) + 1}",
                        heading=heading,
                        level=level,
                        text="\n".join(lines).strip(),
                        order=len(sections),
                    )
                )

        for line in decode(file).splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            match = None if fenced else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if match:
                flush()
                heading, level, lines = match[2], len(match[1]), []
            else:
                lines.append(line)
        flush()
        return document(file, sections, "markdown")
