import Link from "next/link";
import { env } from "@/lib/env";
import { Brand } from "@/components/brand";
import { WorkflowBadge } from "@/components/workflow-badge";
import { RelayLine } from "@/components/relay-line";
import { workflows } from "@/features/workflows/display";

const howItWorks = [
  {
    number: "01",
    title: "Understand",
    description: "Relay interprets what you give it, in context.",
  },
  {
    number: "02",
    title: "Structure",
    description: "It turns that context into typed, proposed actions.",
  },
  {
    number: "03",
    title: "Review",
    description: "You see exactly what Relay plans to change, before it moves.",
  },
  {
    number: "04",
    title: "Relay",
    description: "Approved actions move into the tools you already use.",
  },
];

const integrations = [
  { name: "Notion", role: "Where structured notes and tasks live." },
  { name: "Google Calendar", role: "Where your real availability lives." },
  { name: "GitHub", role: "Where project work gets tracked." },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
      <header className="flex items-center justify-between border-b border-line pb-6">
        <Brand />
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
          A student workflow workspace
        </p>
        <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
          Move from notes to action.
        </h1>
        <p className="mt-7 max-w-xl text-lg leading-8 text-muted">
          Relay turns lectures, deadlines, and project meetings into organized
          work across the tools students already use.
        </p>
        <div className="mt-9 flex flex-wrap gap-4">
          <Link href="/signup" className="button">
            Start a Relay
          </Link>
          <a href="#how-it-works" className="button secondary">
            See how it works
          </a>
        </div>
      </section>

      <section aria-labelledby="workflows-heading" className="py-14">
        <div className="mb-8 max-w-xl">
          <p className="eyebrow">Three ways forward</p>
          <h2 id="workflows-heading" className="mt-3 text-2xl font-semibold">
            Relay&rsquo;s scope, made explicit.
          </h2>
        </div>
        <div className="space-y-10">
          {workflows.map((workflow) => (
            <article key={workflow.key} className="panel">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <WorkflowBadge workflow={workflow} />
                  <h3 className="mt-3 text-2xl font-semibold">
                    {workflow.title}
                  </h3>
                  <p className="mt-2 max-w-lg text-sm leading-6 text-muted">
                    {workflow.headline}
                  </p>
                </div>
              </div>
              <RelayLine
                sources={workflow.sources.map((label) => ({ label }))}
                destinations={workflow.destinations.map((label) => ({
                  label,
                }))}
                status="DRAFT"
                compact
                label={`${workflow.title} pipeline`}
              />
            </article>
          ))}
        </div>
      </section>

      <section
        id="how-it-works"
        aria-labelledby="how-it-works-heading"
        className="scroll-mt-20 py-14"
      >
        <div className="mb-8 max-w-xl">
          <p className="eyebrow">How Relay works</p>
          <h2 id="how-it-works-heading" className="mt-3 text-2xl font-semibold">
            Nothing moves without your review.
          </h2>
        </div>
        <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {howItWorks.map((step) => (
            <li key={step.number} className="border-t-2 border-accent pt-4">
              <span className="mb-3 block text-xs text-muted">
                {step.number}
              </span>
              <p className="font-medium">{step.title}</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                {step.description}
              </p>
            </li>
          ))}
        </ol>
        <p className="mt-8 max-w-xl text-sm text-muted">
          Drafts and approvals are available today. Automated analysis,
          scheduling, and provider connections are coming in later phases — see
          the honesty note below.
        </p>
      </section>

      <section aria-labelledby="integrations-heading" className="py-14">
        <div className="mb-8 max-w-xl">
          <p className="eyebrow">Where your work lives</p>
          <h2 id="integrations-heading" className="mt-3 text-2xl font-semibold">
            Connect once. Relay remembers where your work lives.
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-3">
          {integrations.map((tool) => (
            <article key={tool.name} className="panel">
              <p className="text-lg font-semibold">{tool.name}</p>
              <p className="mt-3 text-sm leading-6 text-muted">{tool.role}</p>
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
