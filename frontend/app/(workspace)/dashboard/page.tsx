"use client";

import Link from "next/link";
import {
  usePendingApprovals,
  useDefinitions,
  useRuns,
  useUser,
} from "@/hooks/queries";
import { ErrorMessage, Loading, PageTitle } from "@/components/ui";
import { RunList } from "@/components/run-list";

const actions = [
  {
    key: "lecture_to_notion",
    slug: "learn",
    title: "Turn a lecture into notes",
    description: "Upload lecture material and create organized study notes.",
    cta: "Create notes",
  },
  {
    key: "study_scheduler",
    slug: "plan",
    title: "Plan my study time",
    description: "Turn tasks and deadlines into a realistic study week.",
    cta: "Plan my week",
  },
  {
    key: "project_meeting",
    slug: "collaborate",
    title: "Process a team meeting",
    description: "Turn a transcript into decisions and assigned tasks.",
    cta: "Process meeting",
  },
] as const;

export default function Dashboard() {
  const user = useUser();
  const definitions = useDefinitions();
  const runs = useRuns();
  const approvals = usePendingApprovals();

  if (
    user.isPending ||
    definitions.isPending ||
    runs.isPending ||
    approvals.isPending
  )
    return <Loading />;
  const error =
    user.error || definitions.error || runs.error || approvals.error;
  if (error) return <ErrorMessage error={error} />;

  const definitionsByKey = Object.fromEntries(
    (definitions.data || []).map((item) => [item.key, item]),
  );
  const workflowKeys = Object.fromEntries(
    (definitions.data || []).map((item) => [item.id, item.key]),
  );
  const recent = runs.data || [];
  const pending = (approvals.data || []).filter(
    (item) => item.status === "PENDING",
  );

  return (
    <>
      <div className="home-intro">
        <PageTitle
          eyebrow={`Welcome back, ${user.data?.name.split(" ")[0]}`}
          title="What are you working on?"
          description="Bring Relay the material you already have. You will review everything before it is saved to your tools."
        />
      </div>
      {!user.data?.onboarding_completed && (
        <p className="notice mb-8">
          Make Relay yours.{" "}
          <Link className="underline" href="/onboarding">
            Finish your setup
          </Link>
        </p>
      )}

      <section className="mb-14" aria-label="Start new work">
        <div className="home-action-grid">
          {actions.map((action, index) => {
            const definition = definitionsByKey[action.key];
            return (
              <article
                key={action.key}
                className={`home-action ${action.slug}`}
              >
                <p className="eyebrow">0{index + 1}</p>
                <h2>{action.title}</h2>
                <p>{action.description}</p>
                {definition?.enabled ? (
                  <Link className="button" href={`/workflows/${action.slug}`}>
                    {action.cta}
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

      {pending.length > 0 && (
        <section className="review-callout mb-14">
          <div>
            <p className="eyebrow">Needs your review</p>
            <h2>
              {pending.length}{" "}
              {pending.length === 1 ? "item needs" : "items need"} your input
            </h2>
            <p>Check the details and confirm what Relay should save.</p>
          </div>
          <Link className="button" href="/approvals">
            Review now
          </Link>
        </section>
      )}

      <section>
        <div className="section-heading-row">
          <div>
            <p className="eyebrow">Pick up where you left off</p>
            <h2 className="section-title mb-0">Recent work</h2>
          </div>
          {recent.length > 0 && (
            <Link href="/runs" className="text-link">
              View activity
            </Link>
          )}
        </div>
        <RunList runs={recent.slice(0, 5)} workflowKeys={workflowKeys} />
      </section>
    </>
  );
}
