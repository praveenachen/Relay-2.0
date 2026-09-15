import Link from "next/link";
import { ConnectionCards } from "@/components/connection-cards";
import { PageTitle } from "@/components/ui";
import { workflows } from "@/features/workflows/display";

const workflowRequirements = {
  learn: "Best after Notion is connected and a notes destination is selected.",
  plan: "Best after Google Calendar is connected and a calendar is selected.",
  collaborate: "Best after Notion and GitHub are connected.",
} as const;

export default function Connections() {
  return (
    <>
      <PageTitle
        eyebrow="Your tools, connected"
        title="Connections"
        description="Manage where Relay can find and save your work. You still confirm changes before anything is created."
      />
      <ConnectionCards />
      <section className="mt-8 rounded-2xl border border-line bg-surface p-6">
        <div className="max-w-3xl">
          <p className="eyebrow">Ready to work</p>
          <h2 className="mt-2 text-2xl font-semibold">
            Put your connections to work
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            Use Notes, Planner, or Projects to bring in your material. Relay
            prepares the result for you to review before saving anything.
          </p>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {workflows.map((workflow) => (
            <article
              key={workflow.key}
              className="rounded-xl border border-line bg-background p-5"
            >
              <p className="eyebrow">{workflow.pillar}</p>
              <h3 className="mt-3 text-lg font-semibold">{workflow.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">
                {workflow.description}
              </p>
              <p className="mt-4 text-xs leading-5 text-muted">
                {workflowRequirements[workflow.slug]}
              </p>
              <Link
                className="button mt-5 inline-flex"
                href={`/workflows/${workflow.slug}`}
              >
                Open {workflow.pillar.toLowerCase()}
              </Link>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
