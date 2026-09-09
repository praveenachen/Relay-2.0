import { z } from "zod";
import { json, request } from "@/lib/api";

export const projectSchema = z.object({
  id: z.guid(),
  user_id: z.guid(),
  name: z.string(),
  course: z.string().nullable(),
  notion_database_id: z.string().nullable(),
  notion_property_mapping: z.record(z.string(), z.json()).nullable(),
  github_repository_owner: z.string().nullable(),
  github_repository_name: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Project = z.infer<typeof projectSchema>;

export const projectMemberSchema = z.object({
  id: z.guid(),
  project_workspace_id: z.guid(),
  display_name: z.string(),
  email: z.string().nullable(),
  notion_identity: z.string().nullable(),
  github_username: z.string().nullable(),
});
export type ProjectMember = z.infer<typeof projectMemberSchema>;

export type ProjectInput = {
  name: string;
  course?: string | null;
  notion_database_id?: string | null;
  notion_property_mapping?: Record<string, unknown> | null;
  github_repository_owner?: string | null;
  github_repository_name?: string | null;
};

export type ProjectMemberInput = {
  display_name: string;
  email?: string | null;
  notion_identity?: string | null;
  github_username?: string | null;
};

export const projects = {
  list: () => request("/projects", projectSchema.array()),
  get: (id: string) => request(`/projects/${id}`, projectSchema),
  create: (data: ProjectInput) =>
    request("/projects", projectSchema, json(data, "POST")),
  update: (id: string, data: ProjectInput) =>
    request(`/projects/${id}`, projectSchema, json(data, "PUT")),
  members: (id: string) =>
    request(`/projects/${id}/members`, projectMemberSchema.array()),
  addMember: (id: string, data: ProjectMemberInput) =>
    request(`/projects/${id}/members`, projectMemberSchema, json(data, "POST")),
  updateMember: (id: string, memberId: string, data: ProjectMemberInput) =>
    request(
      `/projects/${id}/members/${memberId}`,
      projectMemberSchema,
      json(data, "PUT"),
    ),
  removeMember: (id: string, memberId: string) =>
    request(`/projects/${id}/members/${memberId}`, z.undefined(), {
      method: "DELETE",
    }),
};
