import json

from app.ai.base import Message, T
from app.workflows.lecture_notes.schemas import LectureSummary, SummarySection


class FakeLanguageModel:
    """Deterministic extractive demo; not an AI quality substitute."""

    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T:
        source = json.loads(messages[-1].content)
        sections = [
            SummarySection(
                heading=item.get("heading") or "Lecture material",
                text=item["text"][:600],
                source_refs=[{"section_id": item["id"], "page": item.get("source_page_start")}],
            )
            for item in source["sections"]
            if item["text"].strip()
        ]
        result = LectureSummary(
            title=(source.get("title") or "Lecture study notes")[:255],
            overview=sections[0].text[:300],
            sections=sections,
            takeaways=[section.text.split("\n")[0] for section in sections[:5]],
            review_questions=[f"How would you explain {s.heading}?" for s in sections[:5]],
        )
        return response_model.model_validate(result.model_dump())
