import { json, request } from "@/lib/api";
import { eventSchema, runSchema } from "@/lib/schemas";
export const runs = {
  incomplete: () =>
    request("/workflow-runs?incomplete=true&limit=1", runSchema.array()),
  list: () => request("/workflow-runs", runSchema.array()),
  get: (id: string) => request(`/workflow-runs/${id}`, runSchema),
  create: (id: string) =>
    request("/workflow-runs", runSchema, json({ workflow_definition_id: id })),
  events: (id: string) =>
    request(`/workflow-runs/${id}/events`, eventSchema.array()),
};
