"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { auth } from "@/features/auth/api";
import { Brand } from "@/components/brand";
import { ErrorMessage } from "@/components/ui";

export function AuthForm({ signup = false }: { signup?: boolean }) {
  const [validation, setValidation] = useState<string | null>(null);
  const cache = useQueryClient();
  const router = useRouter();
  const mutation = useMutation({
    mutationFn: async (value: {
      name: string;
      email: string;
      password: string;
    }) => {
      if (signup) await auth.signup(value.email, value.password, value.name);
      await auth.login(value.email, value.password);
      return auth.me();
    },
    onSuccess: (user) => {
      cache.clear();
      router.replace(user.onboarding_completed ? "/dashboard" : "/onboarding");
      router.refresh();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = z
      .object({
        email: z.email(),
        password: z
          .string()
          .min(signup ? 12 : 1)
          .max(128),
        name: z
          .string()
          .trim()
          .min(signup ? 1 : 0)
          .max(120),
      })
      .safeParse({
        email: form.get("email"),
        password: form.get("password"),
        name: form.get("name") || "",
      });
    if (!parsed.success) {
      setValidation(parsed.error.issues[0].message);
      return;
    }
    setValidation(null);
    mutation.mutate(parsed.data);
  }
  return (
    <main className="product-shell auth-shell">
      <section className="panel auth-card">
        <Brand />
        <div className="mt-8">
          <p className="eyebrow">{signup ? "Get started" : "Welcome back"}</p>
          <h1 className="mt-2 text-2xl font-semibold">
            {signup ? "Create your Relay account." : "Pick up where you left off."}
          </h1>
          <p className="mt-3 leading-6 text-muted">
            {signup
              ? "Organize school, work, and personal projects in one place."
              : "Sign in to get back to your projects and tasks."}
          </p>
        </div>
        <form onSubmit={submit} className="mt-7 space-y-5">
          {signup && (
            <label className="field">
              Name
              <input name="name" autoComplete="name" required maxLength={120} />
            </label>
          )}
          <label className="field">
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label className="field">
            Password
            <input
              name="password"
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              minLength={signup ? 12 : 1}
              maxLength={128}
              required
            />
          </label>
          {signup && (
            <p className="text-xs text-muted">
              Use 12 or more characters. Your Relay login is separate from your
              connected tools.
            </p>
          )}
          <ErrorMessage
            error={validation ? new Error(validation) : mutation.error}
          />
          <button className="button w-full" disabled={mutation.isPending}>
            {mutation.isPending
              ? "Please wait..."
              : signup
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
        <p className="mt-6 text-sm text-muted">
          {signup ? "Already have an account?" : "New to Relay?"}{" "}
          <Link
            className="font-medium text-accent underline"
            href={signup ? "/login" : "/signup"}
          >
            {signup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
