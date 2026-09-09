# Workflow status UI

Internal workflow, approval, and connection states are backend enums (`DRAFT`, `AWAITING_APPROVAL`, `PARTIALLY_COMPLETED`, ...). None of them are shown to users verbatim. `features/workflows/status.ts` is the single place that maps every internal value to a user-facing presentation, consumed by `<Status>` (`components/ui.tsx`) and by `stagesFor()` for the Relay Line.

## The mapping

```ts
statusFor(value: string): { label; tone; symbol; description }
```

`tone` is one of `neutral | active | success | warning | danger` — a small, fixed set shared with `.status-badge` in `globals.css`. It is deliberately not one color per enum value: `APPROVED` and `COMPLETED` are both `success`, `AWAITING_APPROVAL` and `PLAN_READY` are both `warning`, because the point of the badge is "does this need me, is it moving, or is it done," not "which of twelve states is this."

Examples of the label rewrite:

| Internal | Displayed |
|---|---|
| `AWAITING_APPROVAL` | Needs review |
| `EXECUTING` | Running |
| `PARTIALLY_COMPLETED` | Partially completed |
| `PENDING` (approval request) | Needs review |
| `REVOKED` (connection) | Disconnected |

## Never color alone

`<Status>` always renders an icon (`lucide-react`, mapped by `symbol`) and the text label next to the tone color, so status is legible in grayscale and to screen readers (the label is real text, not `aria-label`-only). `RelayLine` stage nodes additionally vary by *shape* — a check, an X, a clock, or an empty circle — for the same reason.

## Unknown states fail safe

`statusFor()` falls back to a neutral "Unknown state" presentation for any value it doesn't recognize (verified by the `FUTURE_UNKNOWN` case in `tests/presentation.spec.ts`), rather than throwing or rendering the raw enum. Adding a new backend status without a UI update degrades gracefully instead of breaking a page.

## Adding a new status

1. Add the case to `workflowStatuses` (or `otherStatuses` for non-run entities) in `features/workflows/status.ts` with a label, tone, symbol, and one-sentence description.
2. If it affects Relay Line position, add it to the `index` map in `stagesFor()`.
3. Extend `tests/presentation.spec.ts` if the new value needs a specific assertion beyond the "every state has a label and description" loop.

Do not special-case a status inline in a page component — every consumer should go through `statusFor`/`stagesFor` so the mapping stays in one place.
