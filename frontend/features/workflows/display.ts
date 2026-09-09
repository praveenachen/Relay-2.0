import type { Run } from "@/lib/schemas";

export type WorkflowKey =
  "lecture_to_notion" | "study_scheduler" | "project_meeting";
export type Pillar = "learn" | "plan" | "collaborate";
export const workflowDisplay = {
  lecture_to_notion: {
    key: "lecture_to_notion",
    slug: "learn",
    pillar: "LEARN",
    title: "Lecture Notes",
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
      "PDF and DOCX support is planned. Document upload and processing are not available yet.",
  },
  study_scheduler: {
    key: "study_scheduler",
    slug: "plan",
    pillar: "PLAN",
    title: "Study Schedule",
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
      "Relay imports Notion tasks and Google Calendar availability, then a CP-SAT solver -- not a language model -- decides the actual study times.",
  },
  project_meeting: {
    key: "project_meeting",
    slug: "collaborate",
    pillar: "COLLABORATE",
    title: "Project Actions",
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
      "Relay extracts decisions and action items with a language model, but a deterministic planner -- not the model -- decides which typed Notion and GitHub actions get proposed.",
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
