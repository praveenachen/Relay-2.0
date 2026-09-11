import { z } from "zod";
import { json, request } from "@/lib/api";
import { approvalSchema, runSchema } from "@/lib/schemas";

export const sourceReferenceSchema = z.object({
  section_id: z.string(),
  page: z.number().nullable(),
});

export const summarySchema = z.object({
  title: z.string().min(1),
  overview: z.string().min(1),
  key_concepts: z.array(
    z.object({
      name: z.string(),
      explanation: z.string(),
      source_refs: z.array(sourceReferenceSchema),
    }),
  ),
  sections: z.array(
    z.object({
      heading: z.string(),
      text: z.string(),
      source_refs: z.array(sourceReferenceSchema),
    }),
  ),
  definitions: z.array(
    z.object({
      term: z.string(),
      definition: z.string(),
      source_refs: z.array(sourceReferenceSchema),
    }),
  ),
  formulas: z.array(
    z.object({
      expression: z.string(),
      description: z.string().nullable(),
      source_refs: z.array(sourceReferenceSchema),
    }),
  ),
  examples: z.array(
    z.object({
      title: z.string(),
      explanation: z.string(),
      source_refs: z.array(sourceReferenceSchema),
    }),
  ),
  takeaways: z.array(z.string()),
  review_questions: z.array(z.string()),
  quiz_questions: z
    .array(
      z.object({
        question: z.string(),
        answer: z.string(),
        source_refs: z.array(sourceReferenceSchema),
      }),
    )
    .default([]),
});

export type LectureSummary = z.infer<typeof summarySchema>;

const sourceSchema = z
  .object({
    id: z.guid(),
    filename: z.string(),
    content_type: z.string(),
    size_bytes: z.number(),
    checksum: z.string(),
    status: z.enum(["UPLOADED", "PARSED", "FAILED"]),
    metadata: z
      .object({
        filename: z.string(),
        page_count: z.number().nullable(),
        character_count: z.number(),
        parser: z.string(),
      })
      .nullable(),
    sections: z.array(
      z.object({
        id: z.string(),
        heading: z.string().nullable(),
        level: z.number().nullable(),
        order: z.number(),
        source_page_start: z.number().nullable(),
        source_page_end: z.number().nullable(),
      }),
    ),
  })
  .nullable();

export const learnDetailSchema = z.object({
  run: runSchema,
  source: sourceSchema,
  summary: summarySchema.nullable(),
  provider: z.string(),
  stage: z.string().nullable().optional(),
  approval: approvalSchema.nullable(),
  destination: z.string().nullable(),
});

export type LearnDetail = z.infer<typeof learnDetailSchema>;

export const learnConfigSchema = z.object({
  max_upload_bytes: z.number(),
  provider: z.string(),
  notion_publish_mode: z.enum(["mock", "real"]),
});

export const artifactSchema = z.object({
  id: z.guid(),
  provider: z.string(),
  artifact_type: z.string(),
  external_id: z.string(),
  external_url: z.string(),
  created_at: z.string(),
});

export const learn = {
  config: () => request("/workflows/learn/config", learnConfigSchema),
  create: () => request("/workflows/learn", runSchema, { method: "POST" }),
  detail: (id: string) => request(`/workflows/learn/${id}`, learnDetailSchema),
  upload: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/workflows/learn/${id}/documents`, learnDetailSchema, {
      method: "POST",
      body: form,
    });
  },
  parse: (id: string) =>
    request(`/workflows/learn/${id}/parse`, learnDetailSchema, {
      method: "POST",
    }),
  summarize: (id: string) =>
    request(`/workflows/learn/${id}/summarize`, learnDetailSchema, {
      method: "POST",
    }),
  edit: (id: string, summary: LectureSummary, expectedPayload: unknown) =>
    request(
      `/workflows/learn/${id}/summary`,
      learnDetailSchema,
      json({ summary, expected_payload: expectedPayload }, "PUT"),
    ),
  destination: (id: string) =>
    request(`/workflows/learn/${id}/destination`, learnDetailSchema, {
      method: "PUT",
    }),
  execute: (id: string) =>
    request(`/workflows/learn/${id}/execute`, runSchema, { method: "POST" }),
  artifact: (id: string) =>
    request(`/workflows/learn/${id}/artifact`, artifactSchema),
};
