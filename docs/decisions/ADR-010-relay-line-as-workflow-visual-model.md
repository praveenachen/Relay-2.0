# ADR-010-relay-line-as-workflow-visual-model

Status: Accepted for Phase 3

# Context

Phase 3 needed one visual way to show where a workflow run stands — on the landing page (marketing), on a workflow's entry page (before a run exists), and on the run detail page (a real run's real status) — without three unrelated implementations or a generic AI-dashboard look.

# Options Considered

Chat-first UI (a message thread showing progress as text); a generic numbered stepper; a Kanban-style status board; a full workflow graph/DAG visualization; a single reusable "Relay Line" component (source → stages → destination) parameterized by data.

# Decision

Build one data-driven `RelayLine` component (`components/relay-line.tsx`) with a fixed shape — one or more sources, four fixed stages (Source, Understand, Review, Destination), one or more destinations — and reuse it everywhere a workflow's position needs to be shown, from the DRAFT-only preview on a workflow entry page to the live status on a run detail page.

# Rationale

- **Chat-first** contradicts the product identity (Relay is not a chatbot) and hides state behind prose instead of showing it.
- **A generic stepper** communicates "step N of M" but not the source→destination handoff that is the actual product metaphor, and doesn't naturally support Collaborate's branching destinations (Notion + GitHub).
- **Kanban** models many runs at once well (that's what `/runs` already does with `RunList`), but is the wrong grain for "how is *this* run doing" — it front-loads other people's/other runs' state.
- **A full graph/DAG library** is overengineered for four fixed stages and would invite arbitrary topologies the product doesn't have; every real workflow in scope is linear with at most a fan-out at the very end.
- **One parameterized component** keeps the metaphor consistent (a reviewer sees the same shape on the landing page and in a real run), keeps status logic in one place (`stagesFor`/`statusFor`), and costs nothing extra to reuse on the workflow entry pages added in this phase.

# Consequences

Every new workflow surface that needs to show progress must go through `RelayLine` + `stagesFor`/`statusFor` rather than inventing its own status treatment. Branching is expressed only as multiple `destinations`, not as a general graph — a workflow that needs true branching stages would need a design change, not a prop addition. The four-stage shape (Source/Understand/Review/Destination) is treated as fixed product language; a workflow that doesn't fit that shape doesn't fit Relay's story.

# When We Would Reconsider

If a future workflow genuinely needs more than a linear pipeline with a final fan-out (e.g., parallel review stages, conditional branches), re-evaluate whether that workflow needs a different component rather than extending `RelayLine` into a graph layout engine.
