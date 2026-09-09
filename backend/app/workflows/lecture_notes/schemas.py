from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceReference(StrictModel):
    section_id: str
    page: int | None = None


class KeyConcept(StrictModel):
    name: str
    explanation: str
    source_refs: list[SourceReference] = Field(default_factory=list)


class SummarySection(StrictModel):
    heading: str
    text: str
    source_refs: list[SourceReference] = Field(default_factory=list)


class Definition(StrictModel):
    term: str
    definition: str
    source_refs: list[SourceReference] = Field(default_factory=list)


class Formula(StrictModel):
    expression: str
    description: str | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)


class ExampleSummary(StrictModel):
    title: str
    explanation: str
    source_refs: list[SourceReference] = Field(default_factory=list)


class LectureSummary(StrictModel):
    title: str = Field(min_length=1, max_length=255)
    overview: str = Field(min_length=1)
    key_concepts: list[KeyConcept] = Field(default_factory=list)
    sections: list[SummarySection] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    examples: list[ExampleSummary] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)
