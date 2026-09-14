"use client";
import Link from "next/link";
import {
  usePendingApprovals,
  useIncompleteRun,
  useDefinitions,
  useRuns,
  useUser,
} from "@/hooks/queries";
import { displayFor } from "@/features/workflows/display";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";
import { RunList } from "@/components/run-list";

export default function Dashboard() {
  const user = useUser(),
    definitions = useDefinitions(),
    runs = useRuns(),
    approvals = usePendingApprovals(),
    unfinished = useIncompleteRun();
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
      <div className="dashboard-hero mb-10">
        <PageTitle
          eyebrow="Your workspace"
          title={`A clear next step, ${user.data?.name.split(" ")[0]}.`}
          description="Keep your academic work moving, with you in control of what happens next."
        />
        <div className="metric-grid">
          <div className="metric-card">
            <span className="metric-value">{recent.length}</span>
            <span className="text-sm">recent relays</span>
          </div>
          <div className="metric-card">
            <span className="metric-value">{pending.length}</span>
            <span className="text-sm">waiting approvals</span>
          </div>
          <div className="metric-card">
            <span className="metric-value">
              {definitions.data?.length || 0}
            </span>
            <span className="text-sm">student workflows</span>
          </div>
        </div>
      </div>
      {!user.data?.onboarding_completed && (
        <p className="notice mb-8">
          Make Relay yours.{" "}
          <Link className="underline" href="/onboarding">
            Finish your setup
          </Link>
        </p>
      )}
      <div className="mb-12 grid gap-6 lg:grid-cols-[1.35fr_0.85fr]">
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
            <div className="panel interactive">
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
      <section className="mb-12">
        <h2 className="section-title">Start a Relay</h2>
        <p className="mb-5 text-sm text-muted">
          Pick a workflow to upload sources, prepare a draft, and review the
          exact action before Relay writes to your tools.
        </p>
        <div className="grid gap-5 md:grid-cols-3">
          {definitions.data?.map((definition, index) => {
            const display = displayFor(definition.key);
            return (
              <article
                key={definition.id}
                className={`panel interactive workflow-card ${display?.slug || ""}`}
              >
                <p className="eyebrow">0{index + 1} / DRAFT ONLY</p>
                <h3 className="mt-5 text-2xl font-semibold">
                  {definition.name}
                </h3>
                <p className="mb-6 mt-3 min-h-18 text-sm leading-6 text-muted">
                  {definition.description}
                </p>
                {display ? (
                  <Link
                    className="button"
                    href={`/workflows/${display.slug}`}
                    aria-disabled={!definition.enabled}
                  >
                    {definition.enabled
                      ? `Start ${display.pillar.toLowerCase()}`
                      : "Unavailable"}
                  </Link>
                ) : (
                  <button className="button secondary" disabled>
                    Unavailable
                  </button>
                )}
              </article>
            );
          })}
        </div>
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between border-t border-line pt-8">
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
