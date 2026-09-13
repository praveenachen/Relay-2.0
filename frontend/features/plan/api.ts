import { z } from "zod";
import { json, request } from "@/lib/api";
import { approvalSchema, runSchema } from "@/lib/schemas";
import { notionTaskPropertyMappingSchema } from "@/features/connections/api";

export const academicTaskSchema = z.object({
  id: z.string(),
  title: z.string(),
  course: z.string().nullable(),
  deadline: z.string(),
  estimated_minutes: z.number(),
  priority: z.number(),
  status: z.string(),
});
export type AcademicTask = z.infer<typeof academicTaskSchema>;

export const taskMappingIssueSchema = z.object({
  code: z.string(),
  message: z.string(),
  notion_page_id: z.string().nullable(),
  field: z.string().nullable(),
});

export const busyIntervalSchema = z.object({
  start: z.string(),
  end: z.string(),
  source_event_id: z.string().nullable(),
});

export const studySessionSchema = z.object({
  id: z.string().nullable(),
  task_id: z.string(),
  start: z.string(),
  end: z.string(),
  locked: z.boolean(),
});
export type StudySession = z.infer<typeof studySessionSchema>;

export const schedulingConflictSchema = z.object({
  code: z.string(),
  message: z.string(),
  task_id: z.string().nullable(),
  unscheduled_minutes: z.number(),
});

export const schedulingMetricsSchema = z.object({
  tasks_fully_scheduled: z.number(),
  tasks_partially_scheduled: z.number(),
  unscheduled_minutes: z.number(),
  session_count: z.number(),
  average_session_minutes: z.number(),
  deadline_violations: z.number(),
  preference_violations: z.number(),
});

export const schedulingResultSchema = z.object({
  status: z.enum(["OPTIMAL", "FEASIBLE", "INFEASIBLE"]),
  sessions: z.array(studySessionSchema),
  conflicts: z.array(schedulingConflictSchema),
  metrics: schedulingMetricsSchema,
  unscheduled_minutes_by_task: z.record(z.string(), z.number()),
});
export type SchedulingResult = z.infer<typeof schedulingResultSchema>;

export const planSetupSchema = z
  .object({
    stage: z.string(),
    window: z.object({ start: z.string(), end: z.string() }),
    calendar_id: z.string().nullable(),
    notion_database_id: z.string().nullable(),
    notion_mapping: notionTaskPropertyMappingSchema.nullable(),
    tasks: z.array(academicTaskSchema),
    task_issues: z.array(taskMappingIssueSchema),
    busy_intervals: z.array(busyIntervalSchema),
    sessions: z.array(studySessionSchema),
    locked_sessions: z.array(studySessionSchema),
  })
  .nullable();

export const planDetailSchema = z.object({
  run: runSchema,
  setup: planSetupSchema,
  result: schedulingResultSchema.nullable(),
  approval: approvalSchema.nullable(),
});
export type PlanDetail = z.infer<typeof planDetailSchema>;

export const planConfigSchema = z.object({
  scheduler: z.string(),
  calendar_provider: z.string(),
});

export type PlanSetupInput = {
  start: string;
  end: string;
  calendar_id: string | null;
  notion_database_id: string | null;
  notion_mapping: unknown | null;
  tasks: AcademicTask[];
};

export const plan = {
  config: () => request("/workflows/plan/config", planConfigSchema),
  create: () => request("/workflows/plan", runSchema, { method: "POST" }),
  detail: (id: string) => request(`/workflows/plan/${id}`, planDetailSchema),
  setup: (id: string, data: PlanSetupInput) =>
    request(`/workflows/plan/${id}/setup`, planDetailSchema, json(data, "PUT")),
  generate: (id: string, data: PlanSetupInput) =>
    request(
      `/workflows/plan/${id}/generate`,
      planDetailSchema,
      json(data, "PUT"),
    ),
  importTasks: (id: string) =>
    request(`/workflows/plan/${id}/tasks/import`, planDetailSchema, {
      method: "POST",
    }),
  loadAvailability: (id: string) =>
    request(`/workflows/plan/${id}/availability`, planDetailSchema, {
      method: "POST",
    }),
  solve: (id: string) =>
    request(`/workflows/plan/${id}/solve`, planDetailSchema, {
      method: "POST",
    }),
  adjustSessions: (id: string, sessions: StudySession[]) =>
    request(
      `/workflows/plan/${id}/sessions`,
      planDetailSchema,
      json({ sessions }, "PUT"),
    ),
  lockSession: (id: string, sessionId: string, locked: boolean) =>
    request(
      `/workflows/plan/${id}/sessions/${sessionId}/lock`,
      planDetailSchema,
      json({ session_id: sessionId, locked }, "POST"),
    ),
  removeSession: (id: string, sessionId: string) =>
    request(`/workflows/plan/${id}/sessions/${sessionId}`, planDetailSchema, {
      method: "DELETE",
    }),
  requestApproval: (id: string) =>
    request(`/workflows/plan/${id}/approval`, planDetailSchema, {
      method: "POST",
    }),
  execute: (id: string) =>
    request(`/workflows/plan/${id}/execute`, runSchema, { method: "POST" }),
};
