"""Lightweight, dependency-free duplicate detection for task proposals.

Compares normalized/canonicalized text with a token-set (order-independent)
and sequence (order-sensitive) similarity and takes the better of the two, so
that minor wording changes (added filler words, reordered clauses) are caught
without a vector database or embeddings.
"""

import re
from difflib import SequenceMatcher

_STOPWORDS = {
    "a", "an", "the", "on", "in", "of", "to", "for", "and", "or", "with", "at", "by",
}
POSSIBLE_DUPLICATE_THRESHOLD = 0.82


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"[^a-z0-9\s]", " ", value.strip().lower())
    return " ".join(text.split())


def _tokens(value: str | None) -> set[str]:
    return {word for word in normalize_text(value).split() if word not in _STOPWORDS}


def text_similarity(a: str | None, b: str | None) -> float:
    norm_a, norm_b = normalize_text(a), normalize_text(b)
    if not norm_a or not norm_b:
        return 0.0
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if (tokens_a or tokens_b) else 0.0
    order_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
    return max(jaccard, order_ratio)


class DuplicateCandidate:
    __slots__ = ("reference", "title", "description")

    def __init__(self, reference: str, title: str, description: str | None):
        self.reference, self.title, self.description = reference, title, description


def find_possible_duplicate(
    title: str,
    description: str | None,
    candidates: list[DuplicateCandidate],
    *,
    threshold: float = POSSIBLE_DUPLICATE_THRESHOLD,
) -> DuplicateCandidate | None:
    """Return the best-matching candidate at/above `threshold`, or None.

    A conservative comparison: title similarity is the primary signal, and a
    combined title+description score can also qualify a match when both are
    present. Never treats a match below the threshold as a duplicate.
    """
    best: tuple[DuplicateCandidate, float] | None = None
    for candidate in candidates:
        title_score = text_similarity(title, candidate.title)
        score = title_score
        if description and candidate.description:
            description_score = text_similarity(description, candidate.description)
            score = max(score, (title_score + description_score) / 2)
        if score >= threshold and (best is None or score > best[1]):
            best = (candidate, score)
    return best[0] if best else None
