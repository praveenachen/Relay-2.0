from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class UploadedDocument:
    filename: str
    content_type: str
    content: bytes


class DocumentSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    heading: str | None = None
    level: int | None = None
    text: str
    order: int
    source_page_start: int | None = None
    source_page_end: int | None = None


class DocumentMetadata(BaseModel):
    filename: str
    page_count: int | None = None
    character_count: int
    parser: str


class ParsedDocument(BaseModel):
    title: str | None = None
    metadata: DocumentMetadata
    sections: list[DocumentSection]
