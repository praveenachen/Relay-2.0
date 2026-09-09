import json

from pydantic import ValidationError

from app.ai.base import LanguageModel, Message
from app.workflows.lecture_notes.errors import MalformedModelOutput
from app.workflows.project_meeting.models import MeetingAnalysis
from app.workflows.project_meeting.prompts import SYSTEM
from app.workflows.project_meeting.transcript import MeetingTranscript


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
        validate_references(result, transcript)
        return result
