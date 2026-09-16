export type ProjectTask = {
  id: string;
  projectId: string;
  title: string;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  priority: "LOW" | "MEDIUM" | "HIGH";
  dueDate: string | null;
  dueDateTime?: string | null;
  estimate: number | null;
  sourceTitle?: string | null;
  sourceReference?: string | null;
  description?: string | null;
  externalReferences?: { provider: "GITHUB"; label: string; url: string }[];
  server?: boolean;
};

export function projectTaskFromServer(task: ServerTask): ProjectTask {
  return {
    id: task.id,
    projectId: task.project_id,
    title: task.title,
    description: task.description,
    status: task.status,
    priority: task.priority || "MEDIUM",
    dueDate: task.due_date ? localDateValue(task.due_date) : null,
    dueDateTime: task.due_date,
    estimate: task.estimate_minutes,
    sourceTitle: task.source_title,
    sourceReference: task.source_reference,
    externalReferences: task.external_references,
    server: true,
  };
}

export function taskDeadlineValue(task: ProjectTask): string | null {
  if (!task.dueDate) return null;
  if (task.dueDateTime && localDateValue(task.dueDateTime) === task.dueDate) {
    return task.dueDateTime;
  }
  return new Date(`${task.dueDate}T23:59:00`).toISOString();
}

const KEY = "relay-project-tasks";
export function clearProjectTasks() {
  localStorage.removeItem(KEY);
}
import type { ServerTask } from "@/features/sources/api";
import { localDateValue } from "@/lib/datetime";
