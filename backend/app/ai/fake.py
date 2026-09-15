import json
import re
from datetime import datetime

from app.ai.base import Message, T
from app.sources.dates import first_literal_date
from app.sources.schemas import TaskProposal, TaskProposalBatch
from app.workflows.lecture_notes.schemas import LectureSummary, SourceReference, SummarySection
from app.workflows.project_meeting.models import (
    MeetingActionItem,
    MeetingAnalysis,
    MeetingDecision,
    MeetingSourceReference,
)

_PR_REFERENCE = re.compile(r"#\d+")
_DEADLINE_PHRASE = re.compile(
    r"\b(today|tomorrow|next week|next \w+day|\w+day|in \d+ days?)\b", re.IGNORECASE
)


class FakeLanguageModel:
    """Deterministic extractive demo; not an AI quality substitute."""

    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T:
        if response_model is MeetingAnalysis:
            return self._meeting_analysis(messages, response_model)
        if response_model is TaskProposalBatch:
            return self._task_proposals(messages, response_model)
        return self._lecture_summary(messages, response_model)

    def _task_proposals(self, messages: list[Message], response_model: type[T]) -> T:
        source = json.loads(messages[-1].content)
        source_type = str(source["source_type"])
        content = str(source["content"])
        current_user = str(source.get("current_user", "")).strip().lower()
        lines = [line.strip(" \t-*[]") for line in content.splitlines() if line.strip()]
        proposals: list[TaskProposal] = []

        def add(
            title: str,
            line: str,
            *,
            owner: str | None = None,
            due: datetime | None = None,
            confirm: list[str] | None = None,
        ) -> None:
            clean = title.strip().rstrip(".")
            if clean and clean.lower() not in {item.title.lower() for item in proposals}:
                proposals.append(
                    TaskProposal(
                        title=clean[:300],
                        description=line[:2000],
                        due_date=due,
                        priority="MEDIUM",
                        owner=owner,
                        source_reference=line[:180],
                        reason="Proposed from the source content.",
                        needs_confirmation=confirm or [],
                    )
                )

        if source_type == "MEETING_TRANSCRIPT":
            candidates: list[tuple[str | None, str]] = []
            for line in lines:
                speaker, separator, body = line.partition(":")
                owner = speaker.strip() if separator and len(speaker) < 80 else None
                text = body.strip() if separator else line
                match = re.search(
                    r"\b(?:i'll|i will|will|needs? to|should|action:)\s+(.+)",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    candidates.append((owner, match.group(1).strip()))
            own = [item for item in candidates if item[0] and item[0].lower() in current_user]
            chosen = own or [item for item in candidates if not item[0]] or candidates
            for owner, text in chosen[:6]:
                deadline = _DEADLINE_PHRASE.search(text)
                title = re.split(r"\s+by\s+", text, maxsplit=1, flags=re.IGNORECASE)[0]
                confirm: list[str] = []
                if not owner:
                    confirm.append("owner")
                if not deadline:
                    confirm.append("due_date")
                add(title, text, owner=owner, confirm=confirm)
        elif source_type in {"STUDY_GOAL", "PERSONAL_GOAL"}:
            goal = lines[0] if lines else str(source.get("title", "Goal"))
            for title in (
                f"Review what is required for {goal}",
                f"Gather materials for {goal}",
                f"Complete a focused practice step for {goal}",
                f"Review progress and weak areas for {goal}",
            ):
                add(title, goal, confirm=["due_date"])
        else:
            if source_type == "COURSE_OUTLINE":
                keywords: tuple[str, ...] = (
                    "exam", "midterm", "assignment", "project", "presentation", "assessment"
                )
                selected = [
                    line for line in lines if any(word in line.lower() for word in keywords)
                ]
            elif source_type == "ASSIGNMENT_BRIEF":
                keywords = ("submit", "deliver", "due", "write", "create", "complete", "assignment")
                selected = [
                    line for line in lines if any(word in line.lower() for word in keywords)
                ]
                selected = selected or lines
            else:
                selected = lines
            for line in selected[:6]:
                title = re.sub(r"^(?:due\s*:?|deliverable\s*:?|task\s*:?)\s*", "", line, flags=re.I)
                due = first_literal_date(line)
                add(title, line, due=due, confirm=[] if due else ["due_date"])
        if not proposals:
            add(str(source.get("title", "Review source")), content[:500], confirm=["details"])
        return response_model.model_validate(TaskProposalBatch(proposals=proposals).model_dump())

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
            try:
                normalized_text = text.encode("cp1252").decode("utf-8")
            except UnicodeError:
                normalized_text = text
            normalized_text = normalized_text.replace("\u2019", "'").replace("\u2018", "'")
            lower = normalized_text.lower()
            if any(marker in lower for marker in decision_markers):
                decisions.append(
                    MeetingDecision(
                        title=normalized_text[:80],
                        description=normalized_text[:300],
                        source_refs=[MeetingSourceReference(segment_id=segment["id"])],
                    )
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
                pr_match = _PR_REFERENCE.search(normalized_text)
                deadline_match = _DEADLINE_PHRASE.search(lower)
                action_items.append(
                    MeetingActionItem(
                        title=normalized_text[:80],
                        description=normalized_text[:300],
                        owner_name=segment.get("speaker"),
                        deadline_text=deadline_match.group(0) if deadline_match else None,
                        category=category,
                        source_refs=[MeetingSourceReference(segment_id=segment["id"])],
                        confidence="medium",
                        pull_request_reference=(
                            f"PR {pr_match.group(0)}" if (is_review and pr_match) else None
                        ),
                    )
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
                source_refs=[
                    SourceReference(section_id=item["id"], page=item.get("source_page_start"))
                ],
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
