import { ArrowUpRight } from "lucide-react";
import { statusFor } from "@/features/workflows/status";
import Link from "next/link";
import { Run } from "@/lib/schemas";
import { Empty, Status } from "@/components/ui";
import { displayFor, runContext, runTitle } from "@/features/workflows/display";

export function RunList({
  runs,
  workflowKeys,
  detailed = false,
}: {
  detailed?: boolean;
  runs: Run[];
  workflowKeys: Record<string, string>;
}) {
  if (!runs.length)
    return (
      <Empty title="Your next step starts here.">
        Choose Notes, Planner, or Projects when you are ready to begin.
      </Empty>
    );
  return (
    <ul className={`run-list ${detailed ? "run-history" : ""}`}>
      {runs.map((run) => {
        const display = displayFor(workflowKeys[run.workflow_definition_id]);
        const context = runContext(run);
        return (
          <li key={run.id}>
            <Link className="run-card" href={`/runs/${run.id}`}>
              <div>
                <p className="run-card-title">{runTitle(run, display)}</p>
                <p className="run-card-meta">
                  {context ? `${context} · ` : ""}
                  {display?.title || "Work"} ·{" "}
                  {new Date(run.created_at).toLocaleDateString()}
                </p>
              </div>
              {detailed && (
                <div className="run-history-detail">
                  <p>{statusFor(run.status).description}</p>
                  <p className="run-card-meta">
                    Updated{" "}
                    <time dateTime={run.updated_at}>
                      {new Date(run.updated_at).toLocaleString()}
                    </time>
                  </p>
                </div>
              )}
              <span className="run-card-status">
                <Status value={run.status} />
              </span>
              {detailed && (
                <span className="run-open">
                  Open <ArrowUpRight aria-hidden="true" />
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
