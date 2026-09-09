# ADR-012-typed-ai-summary-boundary

Status: Accepted for Phase 4

# Context

Relay has to turn probabilistic model output into data that can be reviewed, edited, approved, and executed deterministically.

# Decision

Use a `LanguageModel` port that returns typed Pydantic models. LEARN requests `LectureSummary`, validates it again after provider return, and rejects invalid source references. The fake provider is the default. The OpenAI provider uses Responses schema parsing with `store=false`.

# Rationale

Typed output makes malformed model responses a normal domain error instead of a late UI or execution surprise. Keeping providers behind a small port lets tests use deterministic summaries and keeps workflow code free of SDK details.

# Consequences

The summary schema becomes part of the workflow contract and must be versioned carefully when real users have pending approvals. The fake provider is useful for tests but should be labeled in the UI and docs because it is extractive demonstration behavior.
