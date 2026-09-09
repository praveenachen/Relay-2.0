# ADR-016-deterministic-notion-block-mapping

Status: Accepted for Phase 5

# Context

Approved LEARN output must map to Notion without a second model call or hidden transformation.

# Decision

Keep `LectureSummary` provider-neutral. Map approved summaries to Notion blocks through `NotionStudyPageMapper`. Omit empty sections, split long rich text, and map compatible formulas to equation blocks.

# Consequences

Notion formatting can evolve inside the mapper without changing the summary schema. The LLM never emits Notion API block JSON.
