import json
import re

from app.ai.base import Message, T
from app.workflows.lecture_notes.schemas import LectureSummary, SummarySection
from app.workflows.project_meeting.models import MeetingAnalysis

_PR_REFERENCE = re.compile(r"#\d+")
_DEADLINE_PHRASE = re.compile(
    r"\b(today|tomorrow|next week|next \w+day|\w+day|in \d+ days?)\b", re.IGNORECASE
)


class FakeLanguageModel:
    """Deterministic extractive demo; not an AI quality substitute."""

    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T:
        if response_model is MeetingAnalysis:
            return self._meeting_analysis(messages, response_model)
        return self._lecture_summary(messages, response_model)

    def _meeting_analysis(self, messages: list[Message], response_model: type[T]) -> T:
        source = json.loads(messages[-1].content)
        segments = source.get("segments", [])
        decision_markers = ("decided", "we'll go with", "agreed", "we should use")
        action_markers = ("i'll", "i will", "can you", "you should", "will handle")
        review_markers = ("review", "pr ", "pull request", "pr#", "pr #")
        technical_markers = ("code", "bug", "implement", "test", "deploy", "api", "database")
        decisions = []
        action_items = []
        for segment in segments:
            text = str(segment.get("text", ""))
            lower = text.lower()
            if any(marker in lower for marker in decision_markers):
                decisions.append(
                    {
                        "title": text[:80],
                        "description": text[:300],
                        "source_refs": [{"segment_id": segment["id"]}],
                    }
                )
            elif any(marker in lower for marker in action_markers):
                is_review = any(m in lower for m in review_markers)
                category = (
                    "REVIEW_REQUEST"
                    if is_review
                    else (
                        "TECHNICAL_TASK"
                        if any(m in lower for m in technical_markers)
                        else "GENERAL_TASK"
                    )
                )
                pr_match = _PR_REFERENCE.search(text)
                deadline_match = _DEADLINE_PHRASE.search(lower)
                action_items.append(
                    {
                        "title": text[:80],
                        "description": text[:300],
                        "owner_name": segment.get("speaker"),
                        "deadline_text": deadline_match.group(0) if deadline_match else None,
                        "category": category,
                        "source_refs": [{"segment_id": segment["id"]}],
                        "confidence": "medium",
                        "pull_request_reference": (
                            f"PR {pr_match.group(0)}" if (is_review and pr_match) else None
                        ),
                    }
                )
        result = MeetingAnalysis(
            summary=f"Discussed {len(segments)} transcript segment(s)." if segments else "",
            decisions=decisions,
            action_items=action_items,
            unresolved_questions=[],
        )
        return response_model.model_validate(result.model_dump())

    def _lecture_summary(self, messages: list[Message], response_model: type[T]) -> T:
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
