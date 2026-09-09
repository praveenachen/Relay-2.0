import Link from "next/link";
import { Run } from "@/lib/schemas";
import { Empty, Status } from "@/components/ui";

export function RunList({
  runs,
  names,
}: {
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
    <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
      {runs.map((run) => (
        <li key={run.id}>
          <Link
            className="flex flex-wrap items-center justify-between gap-3 p-5 hover:bg-background"
            href={`/runs/${run.id}`}
          >
            <div>
              <p className="font-medium">
                {names[run.workflow_definition_id] || "Workflow run"}
              </p>
              <p className="mt-1 text-xs text-muted">
                Created {new Date(run.created_at).toLocaleString()}
              </p>
            </div>
            <Status value={run.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
