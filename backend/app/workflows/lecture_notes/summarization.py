import json

from pydantic import ValidationError

from app.ai.base import LanguageModel, Message
from app.documents.models import DocumentSection, ParsedDocument
from app.workflows.lecture_notes.errors import MalformedModelOutput
from app.workflows.lecture_notes.prompts import SYSTEM
from app.workflows.lecture_notes.schemas import (
    Definition,
    ExampleSummary,
    Formula,
    KeyConcept,
    LectureSummary,
    SummarySection,
)
from app.workflows.lecture_notes.segmentation import estimated_tokens, segment


def chunk_sections(document: ParsedDocument, budget: int) -> list[list[DocumentSection]]:
    chunks: list[list[DocumentSection]] = []
    current: list[DocumentSection] = []
    current_size = 0
    for section in segment(document, budget):
        size = estimated_tokens(section.text)
        if current and current_size + size > budget:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(section)
        current_size += size
    if current:
        chunks.append(current)
    return chunks


def validate_references(summary: LectureSummary, document: ParsedDocument) -> None:
    sources = {section.id: section for section in document.sections}
    items: list[KeyConcept | SummarySection | Definition | Formula | ExampleSummary] = [
        *summary.key_concepts,
        *summary.sections,
        *summary.definitions,
        *summary.formulas,
        *summary.examples,
    ]
    for item in items:
        for ref in item.source_refs:
            source = sources.get(ref.section_id)
            if source is None:
                raise MalformedModelOutput()
            if ref.page is not None and (
                source.source_page_start is None
                or source.source_page_end is None
                or not source.source_page_start <= ref.page <= source.source_page_end
            ):
                raise MalformedModelOutput()


class SummaryService:
    def __init__(self, model: LanguageModel, direct_budget: int, section_budget: int):
        self.model, self.direct_budget, self.section_budget = model, direct_budget, section_budget

    def strategy(self, document: ParsedDocument) -> str:
        size = sum(estimated_tokens(s.text) for s in document.sections)
        return "direct" if size <= self.direct_budget else "hierarchical"

    async def generate(self, document: ParsedDocument) -> LectureSummary:
        try:
            if self.strategy(document) == "direct":
                result = await self._call(document)
            else:
                # Bounded section calls; deterministic ordered aggregation avoids an unbounded
                # final prompt and retains every typed field and section-level reference.
                summaries: list[LectureSummary] = []
                for sections in chunk_sections(document, self.section_budget):
                    part = document.model_copy(update={"sections": sections})
                    summaries.append(await self._call(part))
                result = LectureSummary(
                    title=document.title or summaries[0].title,
                    overview="\n\n".join(s.overview for s in summaries),
                    **{
                        field: [item for summary in summaries for item in getattr(summary, field)]
                        for field in (
                            "key_concepts",
                            "sections",
                            "definitions",
                            "formulas",
                            "examples",
                            "takeaways",
                            "review_questions",
                        )
                    },
                )
            result = LectureSummary.model_validate(result.model_dump())
            validate_references(result, document)
            return result
        except (ValidationError, AttributeError, TypeError, ValueError) as error:
            raise MalformedModelOutput() from error

    async def _call(self, document: ParsedDocument) -> LectureSummary:
        result = await self.model.generate_structured(
            [
                Message(role="system", content=SYSTEM),
                Message(
                    role="user",
                    content=json.dumps(
                        {
                            "title": document.title,
                            "sections": [section.model_dump() for section in document.sections],
                        }
                    ),
                ),
            ],
            LectureSummary,
        )
        result = LectureSummary.model_validate(result.model_dump())
        validate_references(result, document)
        return result
