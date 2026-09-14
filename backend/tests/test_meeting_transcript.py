import pytest

from app.workflows.project_meeting.errors import EmptyTranscript
from app.workflows.project_meeting.transcript import parse_transcript


def test_speaker_colon_format_extracts_speaker_and_text():
    transcript = parse_transcript("Sarah: I'll handle authentication.\n\nAlex: Sounds good.")
    assert [s.speaker for s in transcript.segments] == ["Sarah", "Alex"]
    assert transcript.segments[0].text == "I'll handle authentication."
    assert {p.name for p in transcript.participants} == {"Sarah", "Alex"}


def test_timestamp_speaker_format_extracts_timestamp_and_multiline_text():
    raw = "[10:42] Alex:\nI'll review Sarah's PR.\nIt should be quick."
    transcript = parse_transcript(raw)
    assert len(transcript.segments) == 1
    segment = transcript.segments[0]
    assert segment.speaker == "Alex"
    assert segment.timestamp == "10:42"
    assert segment.text == "I'll review Sarah's PR. It should be quick."


def test_plain_notes_have_no_speaker():
    transcript = parse_transcript("We discussed the database schema.\nEveryone agreed on Postgres.")
    assert len(transcript.segments) == 1
    assert transcript.segments[0].speaker is None


def test_unknown_speaker_mixed_with_named_speakers():
    raw = "Sarah: I'll own the API.\n\nGeneral notes without a speaker.\n\nAlex: I'll review it."
    transcript = parse_transcript(raw)
    assert [s.speaker for s in transcript.segments] == ["Sarah", None, "Alex"]


def test_empty_transcript_raises():
    with pytest.raises(EmptyTranscript):
        parse_transcript("   \n\n   ")


def test_segment_ordering_is_sequential_and_ids_are_stable():
    transcript = parse_transcript("Sarah: First.\n\nAlex: Second.\n\nSarah: Third.")
    assert [s.order for s in transcript.segments] == [0, 1, 2]
    assert [s.id for s in transcript.segments] == ["segment-1", "segment-2", "segment-3"]
    assert [s.text for s in transcript.segments] == ["First.", "Second.", "Third."]


def test_second_colon_in_a_speakers_line_stays_part_of_the_text():
    # The speaker/text split matches on the first colon; a second colon
    # later in the same line (e.g. "Note: ...") stays inside the text
    # rather than being treated as another speaker boundary.
    transcript = parse_transcript("Sarah: Note: I will finish this by Friday.")
    assert transcript.segments[0].speaker == "Sarah"
    assert transcript.segments[0].text == "Note: I will finish this by Friday."


def test_markdown_bold_speaker_format_extracts_speaker_and_text():
    transcript = parse_transcript(
        "**Sarah:** I\u2019ll handle authentication.\n\n**Alex:** Sounds good."
    )
    assert [s.speaker for s in transcript.segments] == ["Sarah", "Alex"]
    assert transcript.segments[0].text == "I'll handle authentication."
    assert {p.name for p in transcript.participants} == {"Sarah", "Alex"}


def test_timestamp_markdown_bold_speaker_format_extracts_timestamp():
    raw = "[10:42] **Alex:**\nI\u2019ll review Sarah\u2019s PR.\nIt should be quick."
    transcript = parse_transcript(raw)
    assert len(transcript.segments) == 1
    segment = transcript.segments[0]
    assert segment.speaker == "Alex"
    assert segment.timestamp == "10:42"
    assert segment.text == "I'll review Sarah's PR. It should be quick."


def test_markdown_metadata_is_not_treated_as_speakers():
    transcript = parse_transcript(
        "**Date:** October 6, 2026\n\n**Project:** StudySync\n\n**Maya:** I will lead demo prep."
    )
    assert [participant.name for participant in transcript.participants] == ["Maya"]
    assert transcript.segments[-1].speaker == "Maya"
