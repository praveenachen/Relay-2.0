"use client";
import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { preferences } from "@/features/preferences/api";
import { usePreferences } from "@/hooks/queries";
import { Preferences, preferenceInput } from "@/lib/schemas";
import { ErrorMessage, Loading, Spinner } from "@/components/ui";

export function PreferencesForm({
  onSaved,
  label = "Save preferences",
}: {
  onSaved?: () => void;
  label?: string;
}) {
  const query = usePreferences();
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorMessage error={query.error} />;
  return (
    <PreferenceFields initial={query.data} onSaved={onSaved} label={label} />
  );
}
function PreferenceFields({
  initial,
  onSaved,
  label,
}: {
  initial: Preferences;
  onSaved?: () => void;
  label: string;
}) {
  const cache = useQueryClient();
  const [validation, setValidation] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: preferences.save,
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["preferences"] });
      onSaved?.();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = preferenceInput.safeParse({
      timezone: form.get("timezone"),
      earliest_study_time: form.get("earliest_study_time"),
      latest_study_time: form.get("latest_study_time"),
      preferred_session_minutes: Number(form.get("preferred_session_minutes")),
      maximum_session_minutes: Number(form.get("maximum_session_minutes")),
      minimum_break_minutes: Number(form.get("minimum_break_minutes")),
    });
    if (!parsed.success) {
      setValidation(
        parsed.error.issues.map((issue) => issue.message).join(" "),
      );
      return;
    }
    setValidation(null);
    mutation.mutate(parsed.data);
  }
  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <label className="field sm:col-span-2">
          Timezone
          <input
            name="timezone"
            defaultValue={initial.timezone}
            placeholder="America/Toronto"
            required
            list="timezones"
          />
          <datalist id="timezones">
            {[
              "UTC",
              "America/Toronto",
              "America/Vancouver",
              "America/New_York",
              "America/Los_Angeles",
              "Europe/London",
              "Asia/Kolkata",
            ].map((zone) => (
              <option key={zone} value={zone} />
            ))}
          </datalist>
        </label>
        <label className="field">
          Earliest study time
          <input
            name="earliest_study_time"
            type="time"
            defaultValue={initial.earliest_study_time.slice(0, 5)}
            required
          />
        </label>
        <label className="field">
          Latest study time
          <input
            name="latest_study_time"
            type="time"
            defaultValue={initial.latest_study_time.slice(0, 5)}
            required
          />
        </label>
        <label className="field">
          Preferred session (minutes)
          <input
            name="preferred_session_minutes"
            type="number"
            min={5}
            max={480}
            step={1}
            defaultValue={initial.preferred_session_minutes}
            required
          />
        </label>
        <label className="field">
          Maximum session (minutes)
          <input
            name="maximum_session_minutes"
            type="number"
            min={5}
            max={480}
            step={1}
            defaultValue={initial.maximum_session_minutes}
            required
          />
        </label>
        <label className="field">
          Minimum break (minutes)
          <input
            name="minimum_break_minutes"
            type="number"
            min={0}
            max={240}
            step={1}
            defaultValue={initial.minimum_break_minutes}
            required
          />
        </label>
      </div>
      <p className="text-sm text-muted">
        Choose a daytime window in your local timezone. These preferences are
        saved for future scheduling.
      </p>
      <ErrorMessage
        error={validation ? new Error(validation) : mutation.error}
      />
      {mutation.isSuccess && !onSaved && (
        <p role="status" className="text-sm text-accent">
          Preferences saved.
        </p>
      )}
      <button className="button" disabled={mutation.isPending}>
        {mutation.isPending && <Spinner label="Saving preferences" />}
        {mutation.isPending ? "Saving..." : label}
      </button>
    </form>
  );
}
