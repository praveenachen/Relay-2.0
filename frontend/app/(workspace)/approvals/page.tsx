"use client";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { approvals } from "@/features/approvals/api";
import { Approval } from "@/lib/schemas";
import { useApprovals } from "@/hooks/queries";
import {
  Empty,
  ErrorMessage,
  Loading,
  PageTitle,
  Status,
} from "@/components/ui";
export default function Approvals() {
  const query = useApprovals(),
    cache = useQueryClient();
  const resolve = useMutation({
    mutationFn: ({
      approval,
      approve,
    }: {
      approval: Approval;
      approve: boolean;
    }) => approvals.resolve(approval, approve),
    onSettled: async () => {
      await Promise.all([
        cache.invalidateQueries({ queryKey: ["approvals"] }),
        cache.invalidateQueries({ queryKey: ["runs"] }),
        cache.invalidateQueries({ queryKey: ["events"] }),
      ]);
    },
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorMessage error={query.error} />;
  return (
    <>
      <PageTitle
        eyebrow="You are in control"
        title="Approvals"
        description="Review the exact proposed payload before making a decision. LEARN approvals can be edited in the review workspace before publishing to the local mock Notion connector."
      />
      <ErrorMessage error={resolve.error} />
      {!query.data.length ? (
        <Empty title="Nothing needs your approval.">
          Future workflow plans will appear here before anything changes in your
          tools.
        </Empty>
      ) : (
        <div className="space-y-5">
          {query.data.map((approval) => (
            <article key={approval.id} className="panel">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Link
                  className="font-medium underline"
                  href={`/workflows/learn/${approval.workflow_run_id}`}
                >
                  Open LEARN review
                </Link>
                <Status value={approval.status} />
              </div>
              <p className="mt-5 text-sm font-medium">
                {approval.status === "APPROVED"
                  ? "Approved payload"
                  : "Proposed payload"}
              </p>
              <pre className="my-4 max-h-96 overflow-auto rounded-lg bg-background p-4 text-xs leading-6">
                {JSON.stringify(
                  approval.approved_payload || approval.original_payload,
                  null,
                  2,
                )}
              </pre>
              {approval.status === "PENDING" && (
                <div className="flex gap-3">
                  <button
                    className="button"
                    disabled={resolve.isPending}
                    onClick={() => resolve.mutate({ approval, approve: true })}
                  >
                    Approve exact payload
                  </button>
                  <button
                    className="button secondary"
                    disabled={resolve.isPending}
                    onClick={() => resolve.mutate({ approval, approve: false })}
                  >
                    Reject
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
