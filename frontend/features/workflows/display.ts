import type { Run } from "@/lib/schemas";

export type WorkflowKey =
  "lecture_to_notion" | "study_scheduler" | "project_meeting";
export type Pillar = "notes" | "planner" | "projects";
export const workflowDisplay = {
  lecture_to_notion: {
    key: "lecture_to_notion",
    slug: "learn",
    pillar: "Notes",
    title: "Notes",
    tone: "learn",
    headline: "Move course material into organized knowledge.",
    description: "Turn lecture notes into organized study notes.",
    sources: ["Lecture notes"],
    destinations: ["Notion"],
    steps: [
      "Provide your lecture notes",
      "Organize and summarize the material",
      "Review the proposed notes",
      "Publish approved notes to Notion",
    ],
    inputLabel: "Lecture notes",
    inputHint:
      "Upload PDF, DOCX, Markdown, or text notes. Relay organizes them into study notes for you to review before saving.",
  },
  study_scheduler: {
    key: "study_scheduler",
    slug: "plan",
    pillar: "Planner",
    title: "Planner",
    tone: "plan",
    headline: "Move academic workload into realistic time.",
    description: "Build a study schedule around your real deadlines.",
    sources: ["Notion tasks", "Calendar"],
    destinations: ["Google Calendar"],
    steps: [
      "Bring in your Notion tasks",
      "Check your calendar and study preferences",
      "Review a realistic study plan",
      "Create approved study blocks",
    ],
    inputLabel: "Tasks and availability",
    inputHint:
      "Bring in your tasks and calendar availability to build a realistic study week.",
  },
  project_meeting: {
    key: "project_meeting",
    slug: "collaborate",
    pillar: "Projects",
    title: "Projects",
    tone: "collaborate",
    headline: "Move group discussion into accountable work.",
    description: "Turn project meetings into assigned work.",
    sources: ["Meeting transcript"],
    destinations: ["Notion", "GitHub"],
    steps: [
      "Provide a meeting transcript",
      "Extract decisions and action items",
      "Review owners and proposed changes",
      "Create approved Notion and GitHub work",
    ],
    inputLabel: "Meeting transcript",
    inputHint:
      "Relay finds decisions and action items, then lets you confirm what should be saved to Notion or created in GitHub.",
  },
} as const;
export const workflows = Object.values(workflowDisplay);
export type WorkflowDisplay = (typeof workflows)[number];
export function displayFor(key?: string): WorkflowDisplay | undefined {
  return workflows.find((workflow) => workflow.key === key);
}
export function displayForSlug(slug?: string): WorkflowDisplay | undefined {
  return workflows.find((workflow) => workflow.slug === slug);
}
export function runTitle(run: Run, display?: WorkflowDisplay): string {
  const title = run.input_payload.title;
  return typeof title === "string" && title.trim()
    ? title
    : `${display?.title || "Relay"} draft`;
}
export function runContext(run: Run): string | undefined {
  const context = run.input_payload.course || run.input_payload.project;
  return typeof context === "string" && context.trim() ? context : undefined;
}
export function friendlyKey(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
