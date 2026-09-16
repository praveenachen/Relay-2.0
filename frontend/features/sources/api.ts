import { z } from "zod";
import { json, request } from "@/lib/api";

export const sourceTypeSchema = z.enum([
  "ASSIGNMENT_BRIEF",
  "COURSE_OUTLINE",
  "STUDY_GOAL",
  "MEETING_TRANSCRIPT",
  "DOCUMENT_BRIEF",
  "PERSONAL_GOAL",
  "NOTES_CHECKLIST",
]);
export type SourceType = z.infer<typeof sourceTypeSchema>;

export const sourceSchema = z.object({
  id: z.guid(),
  project_workspace_id: z.guid(),
  source_type: sourceTypeSchema,
  title: z.string(),
  original_filename: z.string().nullable(),
  status: z.enum(["PROCESSING", "READY", "FAILED"]),
  error_message: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ProjectSource = z.infer<typeof sourceSchema>;

export const proposalPayloadSchema = z.object({
  title: z.string(),
  description: z.string().nullable(),
  due_date: z.string().nullable(),
  estimate_minutes: z.number().nullable(),
  priority: z.enum(["LOW", "MEDIUM", "HIGH"]).nullable(),
  owner: z.string().nullable(),
  source_reference: z.string().nullable(),
  reason: z.string().nullable(),
  needs_confirmation: z.array(z.enum(["due_date", "owner", "details"])),
  source_id: z.guid(),
  project_id: z.guid(),
  possible_duplicate: z.boolean(),
  duplicate_of_title: z.string().nullable(),
});
export type ProposalPayload = z.infer<typeof proposalPayloadSchema>;

export const taskProposalSchema = z.object({
  approval_id: z.guid(),
  run_id: z.guid(),
  action_id: z.guid(),
  status: z.enum(["PENDING", "APPROVED", "REJECTED", "EXPIRED"]),
  project_id: z.guid(),
  project_name: z.string(),
  project_space: z.enum(["SCHOOL", "WORK", "PERSONAL"]),
  source_id: z.guid(),
  source_title: z.string(),
  source_type: sourceTypeSchema,
  proposal: proposalPayloadSchema,
  requested_at: z.string(),
});
export type TaskProposal = z.infer<typeof taskProposalSchema>;

export const serverTaskSchema = z.object({
  id: z.guid(),
  project_id: z.guid(),
  title: z.string(),
  description: z.string().nullable(),
  due_date: z.string().nullable(),
  estimate_minutes: z.number().nullable(),
  priority: z.enum(["LOW", "MEDIUM", "HIGH"]).nullable(),
  status: z.enum(["TODO", "IN_PROGRESS", "DONE"]),
  source_id: z.guid().nullable(),
  source_title: z.string().nullable(),
  source_type: sourceTypeSchema.nullable(),
  source_reference: z.string().nullable(),
  external_references: z.array(
    z.object({
      provider: z.literal("GITHUB"),
      label: z.string(),
      url: z.string(),
    }),
  ),
  created_at: z.string(),
});
export type ServerTask = z.infer<typeof serverTaskSchema>;

export const sources = {
  allTasks: () => request("/tasks", serverTaskSchema.array()),
  list: (projectId: string) =>
    request(`/projects/${projectId}/sources`, sourceSchema.array()),
  tasks: (projectId: string) =>
    request(`/projects/${projectId}/tasks`, serverTaskSchema.array()),
  createTask: (
    projectId: string,
    data: {
      title: string;
      description?: string | null;
      due_date?: string | null;
      estimate_minutes?: number | null;
      priority?: "LOW" | "MEDIUM" | "HIGH" | null;
      status?: "TODO" | "IN_PROGRESS" | "DONE";
    },
  ) =>
    request(
      `/projects/${projectId}/tasks`,
      serverTaskSchema,
      json(data, "POST"),
    ),
  updateTask: (
    projectId: string,
    taskId: string,
    data: {
      title: string;
      description?: string | null;
      due_date?: string | null;
      estimate_minutes?: number | null;
      priority?: "LOW" | "MEDIUM" | "HIGH" | null;
      status: "TODO" | "IN_PROGRESS" | "DONE";
    },
  ) =>
    request(
      `/projects/${projectId}/tasks/${taskId}`,
      serverTaskSchema,
      json(data, "PUT"),
    ),
  create: (
    projectId: string,
    data: {
      sourceType: SourceType;
      title: string;
      content: string;
      file?: File | null;
    },
  ) => {
    const body = new FormData();
    body.set("source_type", data.sourceType);
    body.set("title", data.title);
    if (data.content) body.set("content", data.content);
    if (data.file) body.set("file", data.file);
    return request(`/projects/${projectId}/sources`, sourceSchema, {
      method: "POST",
      body,
    });
  },
};

export const taskProposals = {
  list: () => request("/task-proposals", taskProposalSchema.array()),
  edit: (id: string, payload: ProposalPayload) =>
    request(`/task-proposals/${id}`, taskProposalSchema, json(payload, "PUT")),
  accept: (id: string, payload: ProposalPayload) =>
    request(
      `/task-proposals/${id}/accept`,
      z.object({ task_id: z.guid(), duplicate: z.boolean() }),
      json(payload),
    ),
  reject: (id: string) =>
    request(
      `/task-proposals/${id}/reject`,
      z.object({ status: z.literal("rejected") }),
      { method: "POST" },
    ),
};
