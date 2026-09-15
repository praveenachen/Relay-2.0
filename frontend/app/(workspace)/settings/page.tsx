"use client";
import { FormEvent } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { useUser } from "@/hooks/queries";
import { auth } from "@/features/auth/api";
import { PreferencesForm } from "@/components/preferences-form";
import { ErrorMessage, Loading, PageTitle } from "@/components/ui";
export default function Settings() {
  const user = useUser(),
    cache = useQueryClient();
  const profile = useMutation({
    mutationFn: (name: string) =>
      auth.profile(z.string().trim().min(1).max(120).parse(name)),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["user"] }),
  });
  const resetHistory = useMutation({
    mutationFn: auth.resetHistory,
    onSuccess: async () => {
      await cache.invalidateQueries();
    },
  });
  function resetRelayHistory() {
    const confirmed = window.confirm(
      "Clear Relay activity for this profile? This removes saved work, projects, destinations, and study preferences. Connected accounts stay connected.",
    );
    if (confirmed) resetHistory.mutate();
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    profile.mutate(String(new FormData(event.currentTarget).get("name")));
  }
  if (user.isPending) return <Loading />;
  if (user.error) return <ErrorMessage error={user.error} />;
  return (
    <>
      <PageTitle
        eyebrow="Make it yours"
        title="Settings"
        description="A study rhythm that fits your life starts with your preferences."
      />
      <div className="max-w-3xl space-y-8">
        <section className="panel">
          <h2 className="section-title">Your profile</h2>
          <form className="space-y-5" onSubmit={save}>
            <label className="field">
              Name
              <input
                name="name"
                defaultValue={user.data.name}
                required
                maxLength={120}
              />
            </label>
            <p className="text-sm text-muted">{user.data.email}</p>
            <ErrorMessage error={profile.error} />
            {profile.isSuccess && (
              <p role="status" className="text-sm text-accent">
                Profile saved.
              </p>
            )}
            <button className="button" disabled={profile.isPending}>
              Save profile
            </button>
          </form>
        </section>
        <section className="panel">
          <h2 className="section-title">Your study preferences</h2>
          <PreferencesForm />
        </section>
        <section className="panel">
          <h2 className="section-title">Connected tools</h2>
          <p className="text-sm text-muted">
            Notion, Google Calendar, and GitHub connections are managed
            separately from your Relay account.
          </p>
          <Link className="text-link mt-4 inline-flex" href="/connections">
            Manage connections
          </Link>
        </section>
        <section className="panel">
          <h2 className="section-title">Refresh history</h2>
          <p className="text-sm text-muted">
            Clear saved work, projects, destinations, and study preferences for
            this profile. Your login and connected tools stay connected.
          </p>
          <ErrorMessage error={resetHistory.error} />
          {resetHistory.isSuccess && (
            <p role="status" className="text-sm text-accent">
              Relay history cleared.
            </p>
          )}
          <button
            className="button secondary mt-4"
            disabled={resetHistory.isPending}
            onClick={resetRelayHistory}
          >
            {resetHistory.isPending ? "Clearing..." : "Clear Relay history"}
          </button>
        </section>
      </div>
    </>
  );
}
