import Link from "next/link";
import { env } from "@/lib/env";

const workflows = [
  {
    number: "01",
    title: "Learn",
    description: "Turn lecture notes into clear, structured understanding.",
    route: "Lecture notes → Notion",
  },
  {
    number: "02",
    title: "Plan",
    description: "Make room for meaningful study in your actual week.",
    route: "Tasks + availability → Study schedule",
  },
  {
    number: "03",
    title: "Collaborate",
    description: "Give every meeting a clear next step and an owner.",
    route: "Meeting transcript → Notion + GitHub",
  },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
      <header className="flex items-center justify-between border-b border-line pb-6">
        <Link
          href="/"
          aria-label="Relay home"
          className="text-2xl font-semibold tracking-tight"
        >
          ↗ relay
        </Link>
        <span className="rounded-full border border-line px-3 py-1 text-xs text-muted">
          Your academic workspace
        </span>
      </header>
      <nav aria-label="Account" className="mt-5 flex justify-end gap-4 text-sm">
        <Link href="/login" className="button secondary">
          Sign in
        </Link>
        <Link href="/signup" className="button">
          Create account
        </Link>
      </nav>
      <section className="max-w-3xl pb-14 pt-20">
        <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          A little more clarity. A clear next step.
        </p>
        <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
          Move your academic
          <br />
          work forward.
        </h1>
        <p className="mt-7 max-w-xl text-lg leading-8 text-muted">
          From scattered information to understanding, a realistic plan, and
          actions you approve. Your next step starts here.
        </p>
      </section>
      <section
        aria-label="The Relay Line"
        className="rounded-2xl border border-line bg-surface p-7"
      >
        <ol className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          {["Source", "Understand", "Review", "Destination"].map(
            (step, index) => (
              <li key={step} className="border-t-2 border-accent pt-4">
                <span className="mb-3 block text-xs text-muted">
                  0{index + 1}
                </span>
                <span className="font-medium">{step}</span>
              </li>
            ),
          )}
        </ol>
        <p className="mt-7 text-sm text-muted">
          Your approval is the bridge between a proposal and an external action.
        </p>
      </section>
      <section aria-labelledby="workflows" className="py-14">
        <div className="mb-6 flex items-center justify-between">
          <h2 id="workflows" className="text-lg font-semibold">
            Three ways forward
          </h2>
          <span className="text-xs text-muted">Planned workflows</span>
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {workflows.map((workflow) => (
            <article
              key={workflow.title}
              className="rounded-2xl border border-line p-6"
            >
              <p className="text-xs text-muted">{workflow.number} / PLANNED</p>
              <h3 className="mt-5 text-2xl font-semibold">{workflow.title}</h3>
              <p className="mt-3 min-h-18 text-sm leading-6 text-muted">
                {workflow.description}
              </p>
              <p className="mt-6 border-t border-line pt-4 text-xs text-accent">
                {workflow.route}
              </p>
            </article>
          ))}
        </div>
      </section>
      <footer className="flex flex-wrap justify-between gap-4 border-t border-line py-6 text-xs text-muted">
        <p>
          Drafts and approvals are available. Workflow automation and provider
          OAuth are coming later.
        </p>
        <a
          className="underline underline-offset-4"
          href={`${env.NEXT_PUBLIC_API_BASE_URL}/docs`}
        >
          API documentation ↗
        </a>
      </footer>
    </main>
  );
}
