import { z } from "zod";
import { json, request } from "@/lib/api";
import { userSchema } from "@/lib/schemas";

export const auth = {
  me: () => request("/users/me", userSchema),
  signup: (email: string, password: string, name: string) =>
    request("/auth/register", userSchema, json({ email, password, name })),
  login: (email: string, password: string) =>
    request("/auth/login", z.undefined(), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    }),
  logout: () => request("/auth/logout", z.undefined(), { method: "POST" }),
  profile: (name: string) =>
    request("/users/me", userSchema, json({ name }, "PATCH")),
  finish: () =>
    request("/users/me/onboarding", z.undefined(), { method: "POST" }),
  resetHistory: () =>
    request("/users/me/history/reset", z.undefined(), { method: "POST" }),
};
