import re

from app.connectors.notion.schemas import NotionBlock
from app.workflows.lecture_notes.schemas import LectureSummary, SourceReference

MAX_RICH_TEXT = 1900
EQUATION = re.compile(r"^[\w\s+\-*/^=().,{}\\]+$")


def chunks(text: str, limit: int = MAX_RICH_TEXT) -> list[str]:
    stripped = " ".join(text.split())
    if not stripped:
        return []
    result, current = [], stripped
    while len(current) > limit:
        index = current.rfind(" ", 0, limit)
        if index < limit // 2:
            index = limit
        result.append(current[:index].strip())
        current = current[index:].strip()
    if current:
        result.append(current)
    return result


def paragraph(text: str) -> list[NotionBlock]:
    return [NotionBlock(kind="paragraph", text=part) for part in chunks(text)]


def source_note(refs: list[SourceReference]) -> str | None:
    label = " | ".join(f"{ref.section_id}{f', p. {ref.page}' if ref.page else ''}" for ref in refs)
    return f"Source: {label}" if label else None


class NotionStudyPageMapper:
    def map(self, summary: LectureSummary) -> list[NotionBlock]:
        blocks: list[NotionBlock] = []
        blocks.append(NotionBlock(kind="heading_1", text="Study Notes"))
        blocks.extend(paragraph(summary.overview))
        if summary.sections:
            blocks.append(NotionBlock(kind="heading_2", text="Notes"))
            for section in summary.sections:
                blocks.append(NotionBlock(kind="heading_2", text=section.heading))
                blocks.extend(paragraph(section.text))
                note = source_note(section.source_refs)
                if note:
                    blocks.extend(paragraph(note))
        if summary.key_concepts:
            blocks.append(NotionBlock(kind="heading_2", text="Key Concepts"))
            for concept in summary.key_concepts:
                blocks.append(
                    NotionBlock(
                        kind="bulleted_list_item",
                        text=f"{concept.name}: {concept.explanation}",
                    )
                )
        if summary.definitions:
            blocks.append(NotionBlock(kind="heading_2", text="Definitions"))
            for definition in summary.definitions:
                blocks.append(
                    NotionBlock(
                        kind="bulleted_list_item",
                        text=f"{definition.term}: {definition.definition}",
                    )
                )
        if summary.formulas:
            blocks.append(NotionBlock(kind="heading_2", text="Formulas / Equations"))
            for formula in summary.formulas:
                if EQUATION.fullmatch(formula.expression.strip()):
                    blocks.append(NotionBlock(kind="equation", text=formula.expression.strip()))
                else:
                    blocks.extend(paragraph(formula.expression))
                if formula.description:
                    blocks.extend(paragraph(formula.description))
        if summary.examples:
            blocks.append(NotionBlock(kind="heading_2", text="Examples"))
            for example in summary.examples:
                blocks.append(NotionBlock(kind="heading_2", text=example.title))
                blocks.extend(paragraph(example.explanation))
        main_takeaways = summary.takeaways[:5]
        if main_takeaways:
            blocks.append(NotionBlock(kind="heading_2", text="Takeaways"))
            blocks.extend(
                NotionBlock(kind="bulleted_list_item", text=item)
                for takeaway in main_takeaways
                for item in chunks(takeaway)
            )
        if summary.quiz_questions:
            blocks.append(NotionBlock(kind="heading_2", text="Mini Lecture Quiz"))
            for item in summary.quiz_questions:
                children = paragraph(item.answer)
                note = source_note(item.source_refs)
                if note:
                    children.extend(paragraph(note))
                blocks.append(NotionBlock(kind="toggle", text=item.question, children=children))
        elif summary.review_questions:
            blocks.append(NotionBlock(kind="heading_2", text="Mini Lecture Quiz"))
            blocks.extend(
                NotionBlock(kind="numbered_list_item", text=item)
                for question in summary.review_questions
                for item in chunks(question)
            )
        return blocks[:100]
