import { ArrowUpRight } from "lucide-react";
import { statusFor } from "@/features/workflows/status";
import Link from "next/link";
import { Run } from "@/lib/schemas";
import { Empty, Status } from "@/components/ui";

export function RunList({
  runs,
  names,
  detailed = false,
}: {
  detailed?: boolean;
  runs: Run[];
  names: Record<string, string>;
}) {
  if (!runs.length)
    return (
      <Empty title="Your next step starts here.">
        Create a draft from one of the workflow cards. Nothing will run
        automatically.
      </Empty>
    );
  return (
    <ul className={`run-list ${detailed ? "run-history" : ""}`}>
      {runs.map((run) => {
        const workflowName =
          names[run.workflow_definition_id] || "Workflow run";
        return (
          <li key={run.id}>
            <Link className="run-card" href={`/runs/${run.id}`}>
              <div>
                <p className="run-card-title">{workflowName}</p>
                <p className="run-card-meta">
                  Created {new Date(run.created_at).toLocaleString()}
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
                  Open relay <ArrowUpRight aria-hidden="true" />
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
