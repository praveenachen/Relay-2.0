import { BookOpen, CalendarDays, Users } from "lucide-react";
import type { WorkflowDisplay } from "@/features/workflows/display";
const icons = { learn: BookOpen, plan: CalendarDays, collaborate: Users };
export function WorkflowBadge({
  workflow,
  iconOnly = false,
}: {
  workflow?: WorkflowDisplay;
  iconOnly?: boolean;
}) {
  const Icon = icons[workflow?.slug || "learn"];
  return (
    <span className={`workflow-badge ${workflow?.tone || "learn"}`}>
      <Icon aria-hidden="true" />
      {!iconOnly && <span>{workflow?.pillar || "RELAY"}</span>}
    </span>
  );
}
export function ProviderMark({ name }: { name: string }) {
  const label = name.includes("Calendar")
    ? "G"
    : name === "GitHub"
      ? "GH"
      : name.includes("Notion")
        ? "N"
        : null;
  return (
    <span className="provider-label">
      {label && (
        <span className="provider-mark" aria-hidden="true">
          {label}
        </span>
      )}
      {name}
    </span>
  );
}
