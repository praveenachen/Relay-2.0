import Link from "next/link";
import { BriefcaseBusiness, FolderHeart, GraduationCap } from "lucide-react";
import { Brand } from "@/components/brand";

const spaces = [
  {
    tone: "school",
    icon: GraduationCap,
    title: "School",
    description:
      "Courses, assignments, and exams organized into projects with real deadlines.",
  },
  {
    tone: "work",
    icon: BriefcaseBusiness,
    title: "Work",
    description:
      "Briefs, meetings, and next steps kept together so nothing slips through.",
  },
  {
    tone: "personal",
    icon: FolderHeart,
    title: "Personal",
    description:
      "The plans and goals that matter outside of school and work, in one place.",
  },
] as const;

const steps = [
  {
    number: "01",
    title: "Organize it into a project",
    description: "Turn a class, a brief, or an idea into a project with a clear goal.",
  },
  {
    number: "02",
    title: "Break it into tasks",
    description: "Add the concrete steps, due dates, and priorities as you go.",
  },
  {
    number: "03",
    title: "Turn it into a realistic plan",
    description: "See what's due, what's next, and fit it around your week.",
  },
] as const;

export default function Home() {
  return (
    <div className="product-shell">
      <div className="landing-shell">
        <header className="landing-header">
          <Brand />
          <nav aria-label="Account">
            <Link href="/login" className="button secondary">
              Sign in
            </Link>
            <Link href="/signup" className="button">
              Get started
            </Link>
          </nav>
        </header>

        <section className="landing-hero">
          <div>
            <p className="eyebrow">For students</p>
            <h1>One place to organize everything you&rsquo;re working on.</h1>
            <p className="landing-hero-lead">
              Turn school, work, and personal commitments into organized
              projects, actionable tasks, and realistic plans.
            </p>
            <div className="landing-cta-row">
              <Link href="/signup" className="button">
                Get started
              </Link>
              <Link href="/login" className="button secondary">
                Sign in
              </Link>
            </div>
          </div>
          <div className="panel landing-preview" aria-hidden="true">
            <div className="landing-preview-spaces">
              <span className="school">
                <GraduationCap /> School
              </span>
              <span className="work">
                <BriefcaseBusiness /> Work
              </span>
              <span className="personal">
                <FolderHeart /> Personal
              </span>
            </div>
            <div className="landing-preview-cards">
              <div className="landing-preview-card">
                <h4>Biology Final</h4>
                <div className="project-progress">
                  <span style={{ width: "62%" }} />
                </div>
                <p>3 open tasks &middot; Due Fri</p>
              </div>
              <div className="landing-preview-card work">
                <h4>Client Proposal</h4>
                <div className="project-progress">
                  <span style={{ width: "30%" }} />
                </div>
                <p>5 open tasks &middot; Due Mon</p>
              </div>
            </div>
            <div className="landing-preview-today">
              <p className="eyebrow">Today</p>
              <ul className="mini-task-list">
                <li>
                  <span />
                  <strong>Finish problem set 4</strong>
                  <time>Today</time>
                </li>
                <li>
                  <span />
                  <strong>Prep proposal outline</strong>
                  <time>Today</time>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section className="landing-spaces" aria-labelledby="spaces-heading">
          <p className="eyebrow">Your spaces</p>
          <h2 id="spaces-heading" className="mt-2 text-2xl font-semibold">
            Everything sorted where it belongs.
          </h2>
          <div className="landing-spaces-grid">
            {spaces.map(({ tone, icon: Icon, title, description }) => (
              <article key={tone} className={`landing-space-card ${tone}`}>
                <div className="landing-space-icon">
                  <Icon />
                </div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-steps" aria-labelledby="how-it-works-heading">
          <p className="eyebrow">How it works</p>
          <h2 id="how-it-works-heading" className="mt-2 text-2xl font-semibold">
            From commitments to a plan you can act on.
          </h2>
          <div className="landing-steps-grid">
            {steps.map((step) => (
              <div key={step.number} className="landing-step">
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="landing-footer">
          <Brand />
          <p>Your projects, tasks, and plans &mdash; one place for all of it.</p>
        </footer>
      </div>
    </div>
  );
}
