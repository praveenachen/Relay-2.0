import { z } from "zod";
import { json, request } from "@/lib/api";
import { approvalSchema, runSchema } from "@/lib/schemas";

export const sourceReferenceSchema = z.object({ segment_id: z.string() });

export const decisionSchema = z.object({
  title: z.string(),
  description: z.string(),
  source_refs: z.array(sourceReferenceSchema),
});
export type Decision = z.infer<typeof decisionSchema>;

export const memberCandidateSchema = z.object({
  id: z.string(),
  display_name: z.string(),
});

export const plannedActionSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.enum([
    "GENERAL_TASK",
    "TECHNICAL_TASK",
    "DOCUMENTATION",
    "RESEARCH",
    "REVIEW_REQUEST",
  ]),
  confidence: z.enum(["high", "medium", "low"]),
  source_refs: z.array(sourceReferenceSchema),
  owner_name: z.string().nullable(),
  member_id: z.string().nullable(),
  identity_status: z.enum([
    "resolved",
    "ambiguous",
    "unresolved",
    "unspecified",
  ]),
  identity_candidates: z.array(memberCandidateSchema),
  deadline_text: z.string().nullable(),
  deadline_date: z.string().nullable(),
  destinations: z.array(z.enum(["notion", "github"])),
  labels: z.array(z.string()),
  pull_request_reference: z.string().nullable(),
  pull_request_number: z.number().nullable(),
});
export type PlannedAction = z.infer<typeof plannedActionSchema>;

export const collaborateSourceSchema = z
  .object({
    id: z.string(),
    filename: z.string(),
    content_type: z.string(),
    size_bytes: z.number(),
    status: z.string(),
  })
  .nullable();

export const collaborateProjectSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    course: z.string().nullable(),
    notion_database_id: z.string().nullable(),
    github_repository_owner: z.string().nullable(),
    github_repository_name: z.string().nullable(),
  })
  .nullable();

export const collaborateDetailSchema = z.object({
  run: runSchema,
  project: collaborateProjectSchema,
  source: collaborateSourceSchema,
  stage: z.string().nullable(),
  summary: z.string().nullable(),
  decisions: z.array(decisionSchema),
  unresolved_questions: z.array(z.string()),
  action_items: z.array(plannedActionSchema),
  approvals: z.array(approvalSchema),
});
export type CollaborateDetail = z.infer<typeof collaborateDetailSchema>;

export const collaborateConfigSchema = z.object({
  provider: z.string(),
  notion_publish_mode: z.enum(["mock", "real"]),
  github_publish_mode: z.enum(["mock", "real"]),
});

export const collaborate = {
  config: () =>
    request("/workflows/collaborate/config", collaborateConfigSchema),
  create: (projectId: string) =>
    request(
      "/workflows/collaborate",
      runSchema,
      json({ project_id: projectId }, "POST"),
    ),
  detail: (id: string) =>
    request(`/workflows/collaborate/${id}`, collaborateDetailSchema),
  upload: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request(
      `/workflows/collaborate/${id}/transcript`,
      collaborateDetailSchema,
      {
        method: "POST",
        body: form,
      },
    );
  },
  parse: (id: string, meetingDate?: string) =>
    request(
      `/workflows/collaborate/${id}/parse${meetingDate ? `?meeting_date=${meetingDate}` : ""}`,
      collaborateDetailSchema,
      { method: "POST" },
    ),
  analyze: (id: string) =>
    request(`/workflows/collaborate/${id}/analyze`, collaborateDetailSchema, {
      method: "POST",
    }),
  updateActionItems: (id: string, actionItems: PlannedAction[]) =>
    request(
      `/workflows/collaborate/${id}/action-items`,
      collaborateDetailSchema,
      json({ action_items: actionItems }, "PUT"),
    ),
  requestApproval: (id: string) =>
    request(`/workflows/collaborate/${id}/approval`, collaborateDetailSchema, {
      method: "POST",
    }),
  execute: (id: string) =>
    request(`/workflows/collaborate/${id}/execute`, runSchema, {
      method: "POST",
    }),
};
