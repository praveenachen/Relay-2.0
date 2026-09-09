import pytest

from app.ai.base import Message, T
from app.ai.fake import FakeLanguageModel
from app.workflows.lecture_notes.errors import MalformedModelOutput
from app.workflows.project_meeting.analysis import MeetingAnalysisService
from app.workflows.project_meeting.errors import EmptyTranscript
from app.workflows.project_meeting.models import MeetingAnalysis
from app.workflows.project_meeting.transcript import parse_transcript


def transcript_from(*lines: str):
    return parse_transcript("\n\n".join(lines))


async def test_analysis_extracts_decisions_and_action_items_with_provenance():
    transcript = transcript_from(
        "Sarah: We decided to use Postgres for the database.",
        "Alex: I'll implement the authentication API.",
    )
    analysis = await MeetingAnalysisService(FakeLanguageModel()).generate(transcript)
    assert len(analysis.decisions) == 1
    assert analysis.decisions[0].source_refs[0].segment_id == transcript.segments[0].id
    assert len(analysis.action_items) == 1
    action = analysis.action_items[0]
    assert action.owner_name == "Alex"
    assert action.source_refs[0].segment_id == transcript.segments[1].id


async def test_analysis_classifies_technical_task():
    transcript = transcript_from("Alex: I'll implement the login API and fix the database bug.")
    analysis = await MeetingAnalysisService(FakeLanguageModel()).generate(transcript)
    assert analysis.action_items[0].category == "TECHNICAL_TASK"


async def test_analysis_classifies_review_request():
    transcript = transcript_from("Alex: I'll review Sarah's pull request.")
    analysis = await MeetingAnalysisService(FakeLanguageModel()).generate(transcript)
    assert analysis.action_items[0].category == "REVIEW_REQUEST"


async def test_analysis_leaves_owner_and_deadline_null_when_not_stated():
    transcript = transcript_from("We should probably write more tests at some point.")
    analysis = await MeetingAnalysisService(FakeLanguageModel()).generate(transcript)
    assert analysis.decisions == []
    assert analysis.action_items == []


class StaticModel:
    def __init__(self, analysis: MeetingAnalysis):
        self.analysis = analysis

    async def generate_structured(self, messages: list[Message], response_model: type[T]) -> T:
        return response_model.model_validate(self.analysis.model_dump())


async def test_analysis_rejects_a_source_ref_outside_the_transcript():
    transcript = transcript_from("Sarah: I'll handle deployment.")
    bad_analysis = MeetingAnalysis.model_validate(
        {
            "summary": "",
            "decisions": [],
            "action_items": [
                {
                    "title": "Deploy",
                    "description": "Deploy",
                    "owner_name": "Sarah",
                    "category": "TECHNICAL_TASK",
                    "confidence": "high",
                    "source_refs": [{"segment_id": "not-a-real-segment"}],
                }
            ],
            "unresolved_questions": [],
        }
    )
    with pytest.raises(MalformedModelOutput):
        await MeetingAnalysisService(StaticModel(bad_analysis)).generate(transcript)


def test_empty_transcript_text_is_rejected_before_analysis():
    with pytest.raises(EmptyTranscript):
        parse_transcript("")
