from app.documents.models import DocumentSection, ParsedDocument


def estimated_tokens(text: str) -> int:
    """Conservative UTF-8 byte budget, not an exact tokenizer measurement."""
    return len(text.encode("utf-8"))


def segment(document: ParsedDocument, budget: int) -> list[DocumentSection]:
    result = []
    for section in document.sections:
        if estimated_tokens(section.text) <= budget:
            result.append(section.model_copy())
            continue
        pieces: list[str] = []
        current = ""
        for paragraph in section.text.split("\n\n"):
            if current and estimated_tokens(current + "\n\n" + paragraph) > budget:
                pieces.append(current)
                current = ""
            # Split a single oversized paragraph at whitespace, then characters as last resort.
            for word in paragraph.split(" "):
                if current and estimated_tokens(current + " " + word) > budget:
                    pieces.append(current)
                    current = ""
                for char in (" " if current else "") + word:
                    if estimated_tokens(current + char) > budget:
                        pieces.append(current)
                        current = ""
                    current += char
            current += "\n\n"
        if current.strip():
            pieces.append(current.strip())
        for piece in pieces:
            result.append(section.model_copy(update={"text": piece.strip()}))
    return result
