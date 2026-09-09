import pytest
from pydantic import ValidationError

from app.ai.fake import FakeLanguageModel
from app.documents.models import DocumentMetadata, DocumentSection, ParsedDocument
from app.workflows.lecture_notes.errors import MalformedModelOutput
from app.workflows.lecture_notes.schemas import LectureSummary
from app.workflows.lecture_notes.segmentation import segment
from app.workflows.lecture_notes.summarization import SummaryService, validate_references


def source(text="A vector has a magnitude."):
    return ParsedDocument(
        title="Vectors",
        metadata=DocumentMetadata(
            filename="lecture.md",
            character_count=len(text),
            parser="test",
        ),
        sections=[
            DocumentSection(
                id="s1",
                heading="Vectors",
                text=text,
                order=0,
                source_page_start=7,
                source_page_end=7,
            )
        ],
    )


def test_segmentation():
    small = source()
    assert segment(small, 100) == small.sections
    large = source("First paragraph.\n\n" * 100)
    large.sections.append(DocumentSection(id="s2", heading="Next", text="Next.", order=1))
    pieces = segment(large, 100)
    assert len(pieces) > 2
    assert all(
        p.id == "s1" and p.heading == "Vectors" and p.source_page_start == 7 for p in pieces[:-1]
    )
    assert pieces[-1].id == "s2"
    assert all(len(p.text.encode()) <= 100 for p in pieces)
    assert sum(p.text.count("First paragraph.") for p in pieces) == 100


def test_schema():
    summary = LectureSummary(title="Vectors", overview="A magnitude and direction.")
    assert summary.formulas == [] and summary.key_concepts == []
    for value in [
        {"title": "No overview"},
        {"title": "", "overview": "a"},
        {"title": "A", "overview": "B", "invented": 1},
    ]:
        with pytest.raises(ValidationError):
            LectureSummary.model_validate(value)


async def test_direct_hierarchical_and_invalid_provenance():
    service = SummaryService(FakeLanguageModel(), 100, 80)
    assert service.strategy(source()) == "direct"
    assert (await service.generate(source())).sections[0].source_refs[0].page == 7
    large = source("A vector has direction.\n\n" * 50)
    assert service.strategy(large) == "hierarchical"
    summary = await service.generate(large)
    assert len(summary.sections) > 1
    summary.sections[0].source_refs[0].section_id = "invented"
    with pytest.raises(MalformedModelOutput):
        validate_references(summary, large)
