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
  server?: boolean;
};

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
