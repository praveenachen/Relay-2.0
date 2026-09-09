"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  usePendingApprovals,
  useIncompleteRun,
  useDefinitions,
  useRuns,
  useUser,
} from "@/hooks/queries";
import { runs as runApi } from "@/features/workflow-runs/api";
import { displayFor } from "@/features/workflows/display";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";
import { RunList } from "@/components/run-list";

export default function Dashboard() {
  const user = useUser(),
    definitions = useDefinitions(),
    runs = useRuns(),
    approvals = usePendingApprovals(),
    unfinished = useIncompleteRun();
  const router = useRouter(),
    cache = useQueryClient();
  const create = useMutation({
    mutationFn: runApi.create,
    onSuccess: async (run) => {
      await cache.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/runs/${run.id}`);
    },
  });
  if (
    user.isPending ||
    definitions.isPending ||
    runs.isPending ||
    approvals.isPending ||
    unfinished.isPending
  )
    return <Loading />;
  const error =
    user.error ||
    definitions.error ||
    runs.error ||
    approvals.error ||
    unfinished.error;
  if (error) return <ErrorMessage error={error} />;
  const names = Object.fromEntries(
    (definitions.data || []).map((item) => [item.id, item.name]),
  );
  const recent = runs.data || [];
  const incomplete = unfinished.data?.[0];
  const pending = (approvals.data || []).filter(
    (item) => item.status === "PENDING",
  );
  return (
    <>
      <PageTitle
        eyebrow="Your workspace"
        title={`A clear next step, ${user.data?.name.split(" ")[0]}.`}
        description="Keep your academic work moving, with you in control of what happens next."
      />
      {!user.data?.onboarding_completed && (
        <p className="notice mb-8">
          Make Relay yours.{" "}
          <Link className="underline" href="/onboarding">
            Finish your setup
          </Link>
        </p>
      )}
      <div className="mb-10 grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="section-title">Continue where you left off</h2>
          {incomplete ? (
            <RunList runs={[incomplete]} names={names} />
          ) : (
            <Empty title="A fresh start.">
              Your latest unfinished Relay will appear here.
            </Empty>
          )}
        </section>
        <section>
          <h2 className="section-title">Needs your attention</h2>
          {pending.length ? (
            <div className="panel">
              <p className="text-2xl font-semibold">
                {pending.length}
                {pending.length === 100 ? "+" : ""} pending{" "}
                {pending.length === 1 ? "approval" : "approvals"}
              </p>
              <Link
                className="mt-4 inline-block text-sm text-accent underline"
                href="/approvals"
              >
                Review proposed actions
              </Link>
            </div>
          ) : (
            <Empty title="You are all caught up.">
              There are no actions waiting for your approval.
            </Empty>
          )}
        </section>
      </div>
      <section className="mb-10">
        <h2 className="section-title">Start a Relay</h2>
        <p className="mb-5 text-sm text-muted">
          Create a draft to organize your intent. Automation is coming in a
          later phase.
        </p>
        <div className="grid gap-5 md:grid-cols-3">
          {definitions.data?.map((definition, index) => {
            const display = displayFor(definition.key);
            return (
              <article key={definition.id} className="panel">
                <p className="eyebrow">0{index + 1} / DRAFT ONLY</p>
                <h3 className="mt-5 text-2xl font-semibold">
                  {definition.name}
                </h3>
                <p className="mb-6 mt-3 min-h-18 text-sm leading-6 text-muted">
                  {definition.description}
                </p>
                <div className="flex flex-wrap items-center gap-4">
                  <button
                    className="button secondary"
                    disabled={!definition.enabled || create.isPending}
                    onClick={() => create.mutate(definition.id)}
                  >
                    {!definition.enabled
                      ? "Unavailable"
                      : create.isPending && create.variables === definition.id
                        ? "Creating..."
                        : "Create draft"}
                  </button>
                  {display && (
                    <Link
                      className="text-sm text-accent underline"
                      href={`/workflows/${display.slug}`}
                    >
                      How it works
                    </Link>
                  )}
                </div>
              </article>
            );
          })}
        </div>
        <ErrorMessage error={create.error} />
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="section-title mb-0">Recent Relays</h2>
          <Link href="/runs" className="text-sm text-accent underline">
            View all
          </Link>
        </div>
        <RunList runs={recent.slice(0, 5)} names={names} />
      </section>
    </>
  );
}
