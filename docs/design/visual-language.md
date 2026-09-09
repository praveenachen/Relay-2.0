# Visual language

Relay is a student workflow workspace, not a chatbot with integrations. Every screen should read as structured handoffs between systems (Source → Understand → Review → Destination), not as a conversation with a model. This document is the reference for the tokens and conventions in `frontend/app/globals.css` and the components that consume them.

## Why not generic AI-product design

Gradient blobs, glassmorphism, robot illustrations, and "ask AI anything" boxes signal a generic chat wrapper. Relay's differentiator is that it makes state explicit — draft, needs review, running, done — and shows the path work takes between tools. A calm, editorial, paper-like surface keeps attention on that state instead of on the interface.

## Tokens

Defined once in `:root` in `globals.css`, consumed via Tailwind's `@theme inline` and plain CSS custom properties:

- **Surfaces**: `--background` (warm off-white), `--surface` (card white), `--surface-soft` (recessed panels).
- **Typography color**: `--foreground` for body text, `--muted` for secondary text, `--accent` for interactive/emphasis.
- **Semantic tone**: `--warning`, `--danger`, plus their `-soft` background pairs, used by `.status-badge` and `.notice`.
- **Pillar color**: `--learn`, `--plan`, `--collaborate` — used only by `.workflow-badge` to tag which of the three product pillars a run or page belongs to. These are identity colors, not a general-purpose palette; they should not appear on charts, buttons, or arbitrary UI.
- **Radii**: `--radius-control` (inputs/buttons), `--radius-surface` (cards).
- **Motion**: `--motion-fast` for hover/focus transitions, `--motion-handoff` for state changes on the Relay Line (see [relay-line.md](relay-line.md)).

New components should reuse these tokens and the `.panel` / `.button` / `.field` / `.notice` / `.badge` classes in `globals.css` rather than introducing one-off Tailwind color/spacing values.

## Typography

One sans-serif (`--font-body`) carries almost all interface text — headings, body, labels. A restrained serif (`--font-editorial`) is reserved for the landing page's editorial moments; it is not used inside the authenticated app. Monospace (`--font-system`) is reserved for system metadata: workflow IDs, timestamps, status strings — see `.system-label` and the timeline in `run-detail.tsx`.

## Status without relying on color alone

Every workflow/connection/approval state (`features/workflows/status.ts`) carries a label, a tone, and an icon (`Status` in `components/ui.tsx`). Tone alone is never the only signal — see [workflow-status-ui.md](workflow-status-ui.md).

## Responsiveness and accessibility

Layout breakpoints collapse the three-column Relay Line into a vertical list below 700px (see the `@media (max-width: 700px)` block in `globals.css`). All interactive elements use real `button`/`a` elements with visible `:focus-visible` outlines, and `@media (prefers-reduced-motion: reduce)` disables the pulse/breathe animations used for active states.
