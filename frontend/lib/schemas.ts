import { z } from "zod";

export const workflowStatus = z.enum([
  "DRAFT",
  "ANALYZING",
  "PLAN_READY",
  "AWAITING_APPROVAL",
  "APPROVED",
  "QUEUED",
  "EXECUTING",
  "COMPLETED",
  "PARTIALLY_COMPLETED",
  "FAILED",
  "REJECTED",
  "CANCELLED",
]);
export const providerSchema = z.enum(["GOOGLE", "NOTION", "GITHUB"]);
export type Provider = z.infer<typeof providerSchema>;
export const payloadSchema = z.record(z.string(), z.json());
export const userSchema = z.object({
  id: z.guid(),
  email: z.email(),
  name: z.string(),
  avatar_url: z.string().nullable(),
  onboarding_completed: z.boolean(),
});
export const definitionSchema = z.object({
  id: z.guid(),
  key: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.number(),
  enabled: z.boolean(),
});
export const runSchema = z.object({
  id: z.guid(),
  workflow_definition_id: z.guid(),
  status: workflowStatus,
  input_payload: payloadSchema,
  plan_payload: payloadSchema.nullable(),
  result_payload: payloadSchema.nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
});
export const approvalSchema = z.object({
  id: z.guid(),
  workflow_run_id: z.guid(),
  proposed_action_id: z.guid(),
  status: z.enum(["PENDING", "APPROVED", "REJECTED", "EXPIRED"]),
  original_payload: payloadSchema,
  approved_payload: payloadSchema.nullable(),
  requested_at: z.string(),
  resolved_at: z.string().nullable(),
});
export const connectionSchema = z.object({
  id: z.guid(),
  provider: providerSchema,
  external_account_id: z.string(),
  display_name: z.string(),
  scopes: z.array(z.string()),
  status: z.enum(["CONNECTED", "EXPIRED", "REVOKED", "ERROR"]),
  token_expires_at: z.string().nullable(),
});
export const eventSchema = z.object({
  id: z.guid(),
  event_type: z.string(),
  event_metadata: payloadSchema,
  created_at: z.string(),
});
export const preferenceInput = z
  .object({
    timezone: z
      .string()
      .min(1)
      .refine((value) => {
        try {
          new Intl.DateTimeFormat("en", { timeZone: value });
          return true;
        } catch {
          return false;
        }
      }, "Use a valid timezone, such as America/Toronto."),
    earliest_study_time: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/),
    latest_study_time: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/),
    preferred_session_minutes: z.number().int().min(5).max(480),
    maximum_session_minutes: z.number().int().min(5).max(480),
    minimum_break_minutes: z.number().int().min(0).max(240),
  })
  .superRefine((value, ctx) => {
    if (value.earliest_study_time >= value.latest_study_time)
      ctx.addIssue({
        code: "custom",
        message:
          "Study end must be later than study start. Overnight windows are not supported yet.",
      });
    if (value.preferred_session_minutes > value.maximum_session_minutes)
      ctx.addIssue({
        code: "custom",
        message: "Preferred session length must not exceed your maximum.",
      });
  });
export const preferenceSchema = preferenceInput.safeExtend({
  id: z.guid(),
  user_id: z.guid(),
});
export type Preferences = z.infer<typeof preferenceInput>;
export type User = z.infer<typeof userSchema>;
export type Run = z.infer<typeof runSchema>;
export type Approval = z.infer<typeof approvalSchema>;
