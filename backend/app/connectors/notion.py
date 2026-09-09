from typing import Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from app.domain.errors import DomainError
from app.workflows.lecture_notes.schemas import LectureSummary, StrictModel


class NotionStudyPageContent(StrictModel):
    summary: LectureSummary


class CreateNotionStudyPageAction(StrictModel):
    title: str = Field(min_length=1, max_length=255)
    parent_destination_id: Literal["mock-university-notes"] = "mock-university-notes"
    content: NotionStudyPageContent


class NotionBlock(StrictModel):
    kind: Literal["heading", "paragraph", "bullet", "equation"]
    text: str


class ExternalArtifactResult(StrictModel):
    external_id: str
    external_url: str
    title: str
    simulated: Literal[True] = True
    blocks: list[NotionBlock]


class MockNotionFailure(DomainError):
    code = "MOCK_NOTION_FAILED"
    status_code = 502
    message = "Simulated Notion publishing failed. No page was created."


class NotionConnector(Protocol):
    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult: ...


class NotionStudyPageMapper:
    def map(self, summary: LectureSummary) -> list[NotionBlock]:
        blocks = [NotionBlock(kind="paragraph", text=summary.overview)]
        groups = [
            ("Key concepts", [(v.name, v.explanation) for v in summary.key_concepts]),
            ("Study notes", [(v.heading, v.text) for v in summary.sections]),
            ("Definitions", [(v.term, v.definition) for v in summary.definitions]),
            ("Examples", [(v.title, v.explanation) for v in summary.examples]),
        ]
        for heading, items in groups:
            if items:
                blocks.append(NotionBlock(kind="heading", text=heading))
            for name, text in items:
                blocks.extend(
                    [
                        NotionBlock(kind="heading", text=name),
                        NotionBlock(kind="paragraph", text=text),
                    ]
                )
        for formula in summary.formulas:
            blocks.append(NotionBlock(kind="equation", text=formula.expression))
            if formula.description:
                blocks.append(NotionBlock(kind="paragraph", text=formula.description))
        for heading, values in [
            ("Takeaways", summary.takeaways),
            ("Review questions", summary.review_questions),
        ]:
            if values:
                blocks.append(NotionBlock(kind="heading", text=heading))
            blocks.extend(NotionBlock(kind="bullet", text=value) for value in values)
        return blocks


class MockNotionConnector:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        if self.fail:
            raise MockNotionFailure()
        identifier = "mock-" + uuid5(NAMESPACE_URL, idempotency_key).hex
        return ExternalArtifactResult(
            external_id=identifier,
            external_url=f"mock://notion/page/{identifier}",
            title=action.title,
            blocks=NotionStudyPageMapper().map(action.content.summary),
        )
