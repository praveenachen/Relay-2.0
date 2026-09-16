export type ProjectTask = {
  id: string;
  projectId: string;
  title: string;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  priority: "LOW" | "MEDIUM" | "HIGH";
  dueDate: string | null;
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
    estimate: task.estimate_minutes,
    sourceTitle: task.source_title,
    sourceReference: task.source_reference,
    externalReferences: task.external_references,
    server: true,
  };
}

const KEY = "relay-project-tasks";
const EMPTY = "[]";

export function readTasks(): ProjectTask[] {
  if (typeof window === "undefined") return [];
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(value) ? (value as ProjectTask[]) : [];
  } catch {
    return [];
  }
}

export function writeTasks(tasks: ProjectTask[]) {
  localStorage.setItem(KEY, JSON.stringify(tasks));
  window.dispatchEvent(new Event("relay-tasks-changed"));
}

export function clearProjectTasks() {
  localStorage.removeItem(KEY);
  window.dispatchEvent(new Event("relay-tasks-changed"));
}

function subscribe(callback: () => void) {
  window.addEventListener("relay-tasks-changed", callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener("relay-tasks-changed", callback);
    window.removeEventListener("storage", callback);
  };
}

export function useProjectTasks() {
  const snapshot = useSyncExternalStore(
    subscribe,
    () => localStorage.getItem(KEY) || EMPTY,
    () => EMPTY,
  );
  return useMemo(() => {
    try {
      const value: unknown = JSON.parse(snapshot);
      return Array.isArray(value) ? (value as ProjectTask[]) : [];
    } catch {
      return [];
    }
  }, [snapshot]);
}
import { useMemo, useSyncExternalStore } from "react";
import type { ServerTask } from "@/features/sources/api";
import { localDateValue } from "@/lib/datetime";
