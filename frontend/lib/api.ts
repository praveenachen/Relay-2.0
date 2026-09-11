import { z } from "zod";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const parsed = z
      .object({
        code: z.string().optional(),
        message: z.string().optional(),
        detail: z.unknown().optional(),
      })
      .safeParse(error);
    const code = parsed.success ? parsed.data.code : undefined;
    const detail = parsed.success ? parsed.data.detail : undefined;
    const messages: Record<string, string> = {
      REGISTER_USER_ALREADY_EXISTS:
        "An account with this email already exists. Try signing in.",
      LOGIN_BAD_CREDENTIALS: "Email or password is incorrect.",
      LEARN_WORKFLOW_INVALID_STATE:
        "This step is already running or is not available yet. Wait for the current step to finish, then refresh if needed.",
      INVALID_WORKFLOW_TRANSITION:
        "This workflow is already moving to another step. Wait for the current step to finish, then refresh if needed.",
    };
    const message =
      code && messages[code]
        ? messages[code]
        : typeof detail === "string" && messages[detail]
          ? messages[detail]
          : parsed.success && parsed.data.message
            ? parsed.data.message
            : response.status === 401
              ? "Your session has ended. Please sign in again."
              : "The request could not be completed. Check your details and try again.";
    throw new ApiError(response.status, message);
  }
  const parsed = schema.safeParse(
    response.status === 204 ? undefined : await response.json(),
  );
  if (!parsed.success)
    throw new ApiError(
      502,
      "Relay returned an unexpected response. Please try again later.",
    );
  return parsed.data;
}

export function json(body: unknown, method = "POST"): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
