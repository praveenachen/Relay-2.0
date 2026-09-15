from app.sources.dedupe import DuplicateCandidate, find_possible_duplicate, text_similarity


def test_reworded_title_is_similar_enough_to_flag():
    score = text_similarity(
        "Benchmark retrieval latency on latest dataset",
        "Benchmark retrieval latency on the latest dataset",
    )
    assert score >= 0.9


def test_reordered_title_is_similar_enough_to_flag():
    score = text_similarity(
        "Fix responsive layout on mobile results page",
        "Fix mobile results page responsive layout",
    )
    assert score >= 0.9


def test_genuinely_different_task_is_not_similar():
    score = text_similarity(
        "Benchmark retrieval latency on latest dataset",
        "Write onboarding docs for new hires",
    )
    assert score < 0.5


def test_find_possible_duplicate_matches_reworded_title():
    candidates = [
        DuplicateCandidate("task:1", "Benchmark retrieval latency on latest dataset", None)
    ]
    match = find_possible_duplicate(
        "Benchmark retrieval latency on the latest dataset", None, candidates
    )
    assert match is not None
    assert match.reference == "task:1"


def test_find_possible_duplicate_ignores_unrelated_task():
    candidates = [DuplicateCandidate("task:1", "Write onboarding docs for new hires", None)]
    match = find_possible_duplicate(
        "Benchmark retrieval latency on the latest dataset", None, candidates
    )
    assert match is None
