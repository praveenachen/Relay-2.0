import json
import re

from pydantic import ValidationError

from app.ai.base import LanguageModel, Message
from app.workflows.lecture_notes.errors import MalformedModelOutput
from app.workflows.project_meeting.models import MeetingActionItem, MeetingAnalysis
from app.workflows.project_meeting.prompts import SYSTEM
from app.workflows.project_meeting.transcript import MeetingTranscript

_COMMITMENT_PATTERN = re.compile(
    r"\b(?:i'll|i\s+will|i\s+can|i'm\s+going\s+to|i\s+am\s+going\s+to)\b\s*(?P<body>.+)",
    re.IGNORECASE,
)
_DEADLINE_PATTERN = re.compile(
    r"\b(?:by|before|on)\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+(?:morning|afternoon|evening|night))?|tomorrow|today|tonight|next\s+[A-Za-z]+|[A-Z][A-Za-z]+(?:\s+\d{1,2})?)\b",
    re.IGNORECASE,
)
_FILLER_PATTERN = re.compile(
    r"^(?:yeah|yep|yes|okay|ok|sure|sounds good|works for me)[,\s.]+", re.IGNORECASE
)


def _normalize_commitment_text(value: str) -> str:
    try:
        value = value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        pass
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = re.sub(r"(?<=\bi)[?\ufffd]+(?=ll\b|m\b)", "'", value, flags=re.IGNORECASE)
    return re.sub(r"(?<=\w)[?\ufffd](?=\w)", "'", value).strip()


def _classify_action(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ["pull request", " pr", "review"]):
        return "REVIEW_REQUEST"
    if any(
        token in lower
        for token in [
            "api",
            "bug",
            "code",
            "component",
            "database",
            "deploy",
            "endpoint",
            "github",
            "implement",
            "pr",
            "test",
        ]
    ):
        return "TECHNICAL_TASK"
    if any(token in lower for token in ["doc", "readme", "checklist", "write-up", "writeup"]):
        return "DOCUMENTATION"
    if any(token in lower for token in ["research", "compare", "look into"]):
        return "RESEARCH"
    return "GENERAL_TASK"


def _extract_deadline(text: str) -> str | None:
    match = _DEADLINE_PATTERN.search(text)
    if not match:
        return None
    return match.group(0)


def _clean_title(text: str) -> str:
    cleaned = _FILLER_PATTERN.sub("", text).strip()
    cleaned = re.split(r"\s+(?:by|before|on)\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = cleaned.rstrip(" .")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Follow up on meeting commitment"


def _fallback_action_items(transcript: MeetingTranscript) -> list[MeetingActionItem]:
    items: list[MeetingActionItem] = []
    seen: set[tuple[str | None, str]] = set()
    for segment in transcript.segments:
        text = _normalize_commitment_text(segment.text)
        match = _COMMITMENT_PATTERN.search(text)
        if not match:
            continue
        body = _FILLER_PATTERN.sub("", match.group("body")).strip()
        if not body or body.endswith("?"):
            continue
        title = _clean_title(body)
        key = (segment.speaker, title.lower())
        if key in seen:
            continue
        seen.add(key)
        category = _classify_action(body)
        items.append(
            MeetingActionItem(
                title=title,
                description=body.rstrip(" ."),
                owner_name=segment.speaker,
                deadline_text=_extract_deadline(body),
                category=category,
                source_refs=[{"segment_id": segment.id}],
                confidence="medium",
                pull_request_reference=body if category == "REVIEW_REQUEST" else None,
            )
        )
    return items


def validate_references(analysis: MeetingAnalysis, transcript: MeetingTranscript) -> None:
    valid_ids = {segment.id for segment in transcript.segments}
    for decision in analysis.decisions:
        for ref in decision.source_refs:
            if ref.segment_id not in valid_ids:
                raise MalformedModelOutput()
    for item in analysis.action_items:
        for ref in item.source_refs:
            if ref.segment_id not in valid_ids:
                raise MalformedModelOutput()


class MeetingAnalysisService:
    def __init__(self, model: LanguageModel):
        self.model = model

    async def generate(self, transcript: MeetingTranscript) -> MeetingAnalysis:
        try:
            return await self._call(transcript)
        except (ValidationError, AttributeError, TypeError, ValueError) as error:
            raise MalformedModelOutput() from error

    async def _call(self, transcript: MeetingTranscript) -> MeetingAnalysis:
        payload = {
            "segments": [
                {
                    "id": segment.id,
                    "speaker": segment.speaker,
                    "timestamp": segment.timestamp,
                    "text": segment.text,
                }
                for segment in transcript.segments
            ]
        }
        result = await self.model.generate_structured(
            [
                Message(role="system", content=SYSTEM),
                Message(role="user", content=json.dumps(payload)),
            ],
            MeetingAnalysis,
        )
        result = MeetingAnalysis.model_validate(result.model_dump())
        if not result.action_items:
            fallback_items = _fallback_action_items(transcript)
            if fallback_items:
                result = result.model_copy(update={"action_items": fallback_items})
        validate_references(result, transcript)
        return result
