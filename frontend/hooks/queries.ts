"use client";
import { useQuery } from "@tanstack/react-query";
import { auth } from "@/features/auth/api";
import { definitions } from "@/features/workflow-definitions/api";
import { runs } from "@/features/workflow-runs/api";
import { approvals } from "@/features/approvals/api";
import { connections } from "@/features/connections/api";
import { preferences } from "@/features/preferences/api";
import { projects } from "@/features/projects/api";
import { sources, taskProposals } from "@/features/sources/api";

export const useUser = () => useQuery({ queryKey: ["user"], queryFn: auth.me });
export const useDefinitions = () =>
  useQuery({ queryKey: ["definitions"], queryFn: definitions.list });
export const useRuns = () =>
  useQuery({ queryKey: ["runs"], queryFn: runs.list });
export const useRun = (id: string) =>
  useQuery({ queryKey: ["runs", id], queryFn: () => runs.get(id) });
export const useEvents = (id: string) =>
  useQuery({ queryKey: ["events", id], queryFn: () => runs.events(id) });
export const useApprovals = () =>
  useQuery({ queryKey: ["approvals"], queryFn: approvals.list });
export const useConnections = () =>
  useQuery({ queryKey: ["connections"], queryFn: connections.list });
export const usePreferences = () =>
  useQuery({ queryKey: ["preferences"], queryFn: preferences.get });
export const useProjects = () =>
  useQuery({ queryKey: ["projects"], queryFn: projects.list });
export const useProject = (id: string) =>
  useQuery({ queryKey: ["projects", id], queryFn: () => projects.get(id) });
export const useProjectSources = (id: string) =>
  useQuery({ queryKey: ["projects", id, "sources"], queryFn: () => sources.list(id) });
export const useServerTasks = (id: string) =>
  useQuery({ queryKey: ["projects", id, "tasks"], queryFn: () => sources.tasks(id) });
export const useTaskProposals = () =>
  useQuery({ queryKey: ["task-proposals"], queryFn: taskProposals.list });

export const useIncompleteRun = () =>
  useQuery({ queryKey: ["runs", "incomplete"], queryFn: runs.incomplete });
export const usePendingApprovals = () =>
  useQuery({ queryKey: ["approvals", "pending"], queryFn: approvals.pending });
