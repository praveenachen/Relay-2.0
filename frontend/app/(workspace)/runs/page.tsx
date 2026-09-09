"use client";
import { useState } from "react";
import { useDefinitions, useRuns } from "@/hooks/queries";
import { RunList } from "@/components/run-list";
import { ErrorMessage, Loading, PageTitle } from "@/components/ui";
export default function Runs() {
  const runs = useRuns(),
    definitions = useDefinitions();
  const [filter, setFilter] = useState("");
  if (runs.isPending || definitions.isPending) return <Loading />;
  if (runs.error || definitions.error)
    return <ErrorMessage error={runs.error || definitions.error} />;
  const names = Object.fromEntries(
    (definitions.data || []).map((item) => [item.id, item.name]),
  );
  return (
    <>
      <PageTitle
        eyebrow="Your activity"
        title="Relays"
        description="Every draft has a place. Review your recent runs and see where things stand."
      />
      <label className="field mb-6 max-w-xs">
        Workflow
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="">All workflows</option>
          {definitions.data?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <RunList
        runs={(runs.data || []).filter(
          (run) => !filter || run.workflow_definition_id === filter,
        )}
        names={names}
      />
      <p className="mt-4 text-xs text-muted">Showing up to 50 recent runs.</p>
    </>
  );
}
