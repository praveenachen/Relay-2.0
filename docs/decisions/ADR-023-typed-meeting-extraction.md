# ADR-023-typed-meeting-extraction

Status: Accepted for Phase 7

# Context

A meeting transcript is unstructured, multi-speaker text. COLLABORATE needs decisions, action items, owners, deadlines, and technical classifications out of it, but per the project's core constraint, the model that reads the transcript must not be the thing that decides what happens to Notion or GitHub.

# Decision

`MeetingAnalysisService` (`app/workflows/project_meeting/analysis.py`) calls the existing `LanguageModel.generate_structured` abstraction (the same one LEARN uses) with a single typed response model, `MeetingAnalysis` (`app/workflows/project_meeting/models.py`): a summary, a list of `MeetingDecision`, a list of `MeetingActionItem` (title, description, owner_name, deadline_text, category, source_refs, confidence, pull_request_reference), and unresolved questions. The prompt explicitly forbids inventing an owner, a deadline, or a pull request number -- those fields must be null when the transcript doesn't state them. Every decision and action item must cite the segment id(s) it came from; `validate_references` rejects the whole analysis (`MalformedModelOutput`) if a cited id doesn't exist in the transcript that was actually sent.

# Rationale

This mirrors LEARN's `LectureSummary` + `validate_references` pattern (ADR-012, ADR-013) rather than inventing a new extraction boundary: a single structured response type, grounded against the real source, with nulls instead of guesses for anything the source doesn't state. Reusing the pattern (and, pragmatically, LEARN's `MalformedModelOutput`/`ModelUnavailable`/`ModelTimeout`/`ModelRateLimited` error classes, since they're raised by the shared `OpenAIProvider` regardless of caller) keeps one AI-boundary contract in the codebase instead of two subtly different ones.

# Consequences

Deadlines are deliberately *not* resolved to calendar dates by the model -- see ADR-024 and `app/workflows/project_meeting/deadlines.py` for the separate, deterministic resolver. A `FakeLanguageModel` extension (`app/ai/fake.py`) provides a keyword-based, fully deterministic `MeetingAnalysis` for `LANGUAGE_MODEL_PROVIDER=fake` so tests and CI never need a live model. The shared LEARN-named error classes mean a COLLABORATE analysis failure surfaces LEARN's message text ("Study notes could not be generated...") with the correct status code -- a cosmetic mismatch tracked in `docs/workflows/collaborate.md`'s known limitations rather than fixed by forking the AI error module in this phase.

# When We Would Reconsider

If a third workflow needs typed extraction with materially different grounding rules (e.g. no source-reference requirement at all), hoist the shared validation/error pattern into a workflow-neutral module instead of continuing to import from `lecture_notes`.
