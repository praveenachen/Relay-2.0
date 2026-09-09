# The Relay Line

`components/relay-line.tsx` is Relay's one visual signature: a single reusable component that renders any workflow as a path from source(s), through stages, to destination(s).

## Why it exists

The product name is a metaphor for handoff — information moving between systems with a human decision at the middle. A generic stepper or Kanban board does not carry that metaphor; a line with named endpoints does. Rather than build a bespoke diagram per workflow (Learn, Plan, Collaborate) or per surface (landing page, dashboard, run detail), every place that needs to show "where is this in its journey" renders the same component with different data. See ADR-010 for the alternatives considered and why this shape won.

## API

```ts
type RelayEndpoint = { label: string; icon?: ReactNode; description?: string };

<RelayLine
  sources={RelayEndpoint[]}       // defaults to [{ label: "Your input" }]
  destinations={RelayEndpoint[]}  // defaults to [{ label: "Your tools" }]
  stages={RelayStage[]}           // optional; derived from `status` via stagesFor() when omitted
  status={Run["status"]}          // drives the default stage derivation
  compact={boolean}                // hides the caption; used for marketing/summary contexts
  label={string}                   // accessible name for the figure
/>
```

`stagesFor(status, failedFrom?)` in `features/workflows/status.ts` maps a workflow's internal status onto four fixed stages — Source, Understand, Review, Destination — each with a `state` of `upcoming | waiting | active | complete | failed`. A `FAILED` or `CANCELLED` run passes `failedFrom` (the status it was in before failing) so the line freezes at the stage where things stopped, instead of resetting to the start.

## Where it's used

- **Run detail** (`components/run-detail.tsx`) — the authoritative use: real `status`, no `compact`, full caption.
- **Workflow entry pages** (`components/workflow-entry.tsx`) — shown before any run exists, with `status="DRAFT"` and the workflow's real source/destination labels, so a first-time visitor sees the shape of the pipeline before committing to it.
- **Landing page** (`app/page.tsx`) — `compact` mode, one per pillar, to make the three workflows concrete without a screenshot.

## What it deliberately does not do

It is not a graph library. Branching (e.g. Collaborate writing to both Notion and GitHub) is expressed by listing multiple `destinations`, not by a general DAG layout — the visual stays a single horizontal line with a fan-out only at the very end, matching the mockups in the phase brief. If a future workflow needs actual branching *stages* (not just multiple destinations), that is a sign that the workflow should be modeled as two Relay Lines, not that this component should grow a layout engine.

## Responsive and motion behavior

Below 700px the three-column grid (sources / stages / destinations) becomes a vertical stack; the connecting line rotates from horizontal to vertical via the stage `::before`/`::after` pseudo-elements. The `active` stage gets a `box-shadow` pulse (`breathe` keyframe) to read as "in progress"; this and all other animation is disabled under `prefers-reduced-motion: reduce`.
