"use client";

import Link from "next/link";
import { useDefinitions, usePendingApprovals, useRuns } from "@/hooks/queries";
import { displayFor, runTitle } from "@/features/workflows/display";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";

const reviewCopy = {
  learn: {
    label: "Study notes",
    reason: "Check the notes and choose where to save them.",
    action: "Review notes",
  },
  plan: {
    label: "Study plan",
    reason: "Check the study sessions before adding them to your calendar.",
    action: "Review plan",
  },
  collaborate: {
    label: "Project tasks",
    reason: "Confirm owners and destinations before creating tasks.",
    action: "Review tasks",
  },
} as const;

export default function Approvals() {
  const approvals = usePendingApprovals();
  const runs = useRuns();
  const definitions = useDefinitions();

  if (approvals.isPending || runs.isPending || definitions.isPending)
    return <Loading />;
  const error = approvals.error || runs.error || definitions.error;
  if (error) return <ErrorMessage error={error} />;

  const definitionsById = Object.fromEntries(
    (definitions.data || []).map((item) => [item.id, item]),
  );
  const runsById = Object.fromEntries(
    (runs.data || []).map((run) => [run.id, run]),
  );

  return (
    <>
      <PageTitle
        eyebrow="Your action inbox"
        title="Review"
        description="Only work that needs your input appears here. Open an item to check the details and decide what gets saved."
      />
      {!approvals.data?.length ? (
        <Empty title="You are all caught up.">
          Nothing needs your review right now.
        </Empty>
      ) : (
        <ul className="review-list">
          {approvals.data.map((approval) => {
            const run = runsById[approval.workflow_run_id];
            const definition = run
              ? definitionsById[run.workflow_definition_id]
              : undefined;
            const display = displayFor(definition?.key);
            const copy = display ? reviewCopy[display.slug] : undefined;
            const payloadTitle = approval.original_payload.title;
            const title =
              typeof payloadTitle === "string" && payloadTitle.trim()
                ? payloadTitle
                : run
                  ? runTitle(run, display)
                  : copy?.label || "Saved work";
            const kind = run?.input_payload.kind;
            const href =
              definition?.key === "source_to_tasks"
                ? "/inbox"
                : run?.project_workspace_id &&
                    kind === "project_task_github_issue"
                  ? `/projects/${run.project_workspace_id}?tab=tasks`
                  : run?.project_workspace_id &&
                      kind === "publish_notion_project"
                    ? `/projects/${run.project_workspace_id}`
                    : run?.project_workspace_id && display?.slug === "plan"
                      ? `/projects/${run.project_workspace_id}?tab=plan`
                      : display
                        ? `/workflows/${display.slug}/${approval.workflow_run_id}`
                        : `/runs/${approval.workflow_run_id}`;

            return (
              <li key={approval.id}>
                <article className="review-item">
                  <div className="review-item-copy">
                    <p className="eyebrow">
                      {copy?.label || "Ready to review"}
                    </p>
                    <h2>{title}</h2>
                    <p>
                      {copy?.reason ||
                        "Check the details before Relay saves anything."}
                    </p>
                    <time dateTime={approval.requested_at}>
                      Requested{" "}
                      {new Date(approval.requested_at).toLocaleDateString()}
                    </time>
                  </div>
                  <Link className="button" href={href}>
                    {copy?.action || "Open review"}
                  </Link>
                </article>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
