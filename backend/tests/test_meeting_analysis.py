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


async def test_analysis_handles_markdown_transcript_speakers_and_smart_apostrophes():
    transcript = transcript_from(
        "**Ethan:** I\u2019ll fix mobile responsiveness, switch the components to the "
        "course colour from the API, and then open the PR.",
        "**Daniel:** I\u2019ll create a GitHub issue called Standardize deadline "
        "timestamps to UTC.",
        "**Sarah:** I\u2019ll add the unscheduled_hours value by Thursday morning.",
    )

    analysis = await MeetingAnalysisService(FakeLanguageModel()).generate(transcript)

    assert {participant.name for participant in transcript.participants} == {
        "Ethan",
        "Daniel",
        "Sarah",
    }
    assert len(analysis.action_items) == 3
    assert {item.owner_name for item in analysis.action_items} == {"Ethan", "Daniel", "Sarah"}
    assert any("mobile responsiveness" in item.title for item in analysis.action_items)


async def test_analysis_falls_back_to_commitments_when_model_misses_action_items():
    transcript = transcript_from(
        "**Ethan:** I???ll fix mobile responsiveness and open the PR tomorrow.",
        "**Daniel:** I will add tests for the deadline bug by Wednesday.",
    )
    model_analysis = MeetingAnalysis.model_validate(
        {
            "summary": "The team discussed implementation tasks.",
            "decisions": [],
            "action_items": [],
            "unresolved_questions": [],
        }
    )

    analysis = await MeetingAnalysisService(StaticModel(model_analysis)).generate(transcript)

    assert len(analysis.action_items) == 2
    assert {item.owner_name for item in analysis.action_items} == {"Ethan", "Daniel"}
    assert any("mobile responsiveness" in item.title for item in analysis.action_items)
    assert any(item.deadline_text == "by Wednesday" for item in analysis.action_items)
