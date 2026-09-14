import re

from app.workflows.lecture_notes.schemas import StrictModel
from app.workflows.project_meeting.errors import EmptyTranscript


class MeetingParticipant(StrictModel):
    name: str


class MeetingSegment(StrictModel):
    id: str
    speaker: str | None = None
    order: int
    timestamp: str | None = None
    text: str


class MeetingTranscript(StrictModel):
    participants: tuple[MeetingParticipant, ...]
    segments: tuple[MeetingSegment, ...]


def _normalize_text(value: str) -> str:
    try:
        value = value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        pass
    value = (
        value.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return re.sub(r"(?<=\w)[?\ufffd](?=\w)", "'", value)


def _clean_speaker(value: str) -> str:
    return value.strip().strip("*_").strip()


# "[10:42] Alex:" or "[10:42] **Alex:**" on its own line -- the following line(s) are Alex's text.
_TIMESTAMP_SPEAKER_LINE = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s*(?:\*\*)?(?P<speaker>[^:*][^:]{0,39}):(?:\*\*)?\s*$"
)
# "Sarah: I'll handle authentication." or "**Sarah:** I'll handle authentication." -- speaker
# and text on one line.
# The speaker name is deliberately short and word-like so an ordinary
# sentence containing a colon ("Note: see attached doc") is not mistaken
# for a speaker turn; this is a heuristic, not a guarantee -- transcripts
# with unusual naming conventions may still be misread as plain notes.
_SPEAKER_LINE = re.compile(
    r"^(?:\*\*)?(?P<speaker>[A-Z][A-Za-z .'-]{0,39}):(?:\*\*)?\s*(?P<text>\S.*)$"
)
_IGNORED_SPEAKER_LABELS = {"date", "project", "meeting type", "participants"}


def parse_transcript(raw_text: str) -> MeetingTranscript:
    segments: list[MeetingSegment] = []
    participants: dict[str, None] = {}
    order = 0
    pending_speaker: str | None = None
    pending_timestamp: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal order
        text = " ".join(part for part in buffer if part.strip()).strip()
        buffer.clear()
        if not text:
            return
        segments.append(
            MeetingSegment(
                id=f"segment-{order + 1}",
                speaker=pending_speaker,
                order=order,
                timestamp=pending_timestamp,
                text=text,
            )
        )
        if pending_speaker:
            participants[pending_speaker] = None
        order += 1

    for raw_line in _normalize_text(raw_text).splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            pending_speaker = None
            pending_timestamp = None
            continue
        timestamp_match = _TIMESTAMP_SPEAKER_LINE.match(line)
        if timestamp_match:
            flush()
            pending_speaker = _clean_speaker(timestamp_match.group("speaker"))
            pending_timestamp = timestamp_match.group("timestamp").strip()
            continue
        speaker_match = _SPEAKER_LINE.match(line)
        if speaker_match:
            speaker = _clean_speaker(speaker_match.group("speaker"))
            if speaker.lower() in _IGNORED_SPEAKER_LABELS:
                buffer.append(line)
                continue
            flush()
            pending_speaker = speaker
            pending_timestamp = None
            buffer.append(speaker_match.group("text"))
            continue
        buffer.append(line)
    flush()

    if not segments:
        raise EmptyTranscript()

    return MeetingTranscript(
        participants=tuple(MeetingParticipant(name=name) for name in participants),
        segments=tuple(segments),
    )
