import Link from "next/link";
import { ConnectionCards } from "@/components/connection-cards";
import { PageTitle } from "@/components/ui";

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
            Add sources and tasks to a project, plan your week, and review
            external changes before saving them.
          </p>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {(["school", "work", "personal"] as const).map((space) => (
            <article
              key={space}
              className="rounded-xl border border-line bg-background p-5"
            >
              <h3 className="text-lg font-semibold">
                {space[0].toUpperCase() + space.slice(1)}
              </h3>
              <Link
                className="button mt-5 inline-flex"
                href={`/spaces/${space}`}
              >
                Open {space}
              </Link>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
