"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { auth } from "@/features/auth/api";
import { BookOpen, CalendarDays, Users } from "lucide-react";
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
    <main className="auth-layout">
      <section className="auth-primary">
        <Brand />
        <div className="mt-12">
          <p className="eyebrow">Your academic workspace</p>
          <h1 className="mt-3 text-3xl font-semibold">
            {signup ? "Make room for what matters." : "Welcome back."}
          </h1>
          <p className="mt-4 leading-7 text-muted">
            {signup
              ? "Create your Relay account. Connect your tools whenever you are ready."
              : "Sign in to pick up where you left off."}
          </p>
        </div>
        <form onSubmit={submit} className="mt-8 space-y-5">
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
        <p className="mt-7 text-sm text-muted">
          {signup ? "Already have an account?" : "New to Relay?"}{" "}
          <Link
            className="font-medium text-accent underline"
            href={signup ? "/login" : "/signup"}
          >
            {signup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
      <aside className="auth-context" aria-label="How Relay works">
        <p className="eyebrow">A little less busywork</p>
        <h2>
          Your next step,
          <br />a little clearer.
        </h2>
        <p className="text-muted">
          Bring your material. Make a plan. Review what happens next.
        </p>
        <ul className="auth-workflows">
          <li data-workflow="learn">
            <BookOpen aria-hidden="true" />
            <div>
              <h3>Learn</h3>
              <p>Lecture material to study notes in Notion.</p>
            </div>
          </li>
          <li data-workflow="plan">
            <CalendarDays aria-hidden="true" />
            <div>
              <h3>Plan</h3>
              <p>Study tasks to a schedule that fits your calendar.</p>
            </div>
          </li>
          <li data-workflow="collaborate">
            <Users aria-hidden="true" />
            <div>
              <h3>Collaborate</h3>
              <p>
                Meeting transcripts to project actions in Notion and GitHub.
              </p>
            </div>
          </li>
        </ul>
        <p className="auth-review">You review. Relay carries it forward.</p>
      </aside>
    </main>
  );
}
