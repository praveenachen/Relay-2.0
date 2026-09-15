"use client";
import { useState } from "react";
import { useDefinitions, useRuns } from "@/hooks/queries";
import { RunList } from "@/components/run-list";
import { ErrorMessage, Loading, PageTitle } from "@/components/ui";
import { displayFor } from "@/features/workflows/display";
export default function Runs() {
  const runs = useRuns(),
    definitions = useDefinitions();
  const [filter, setFilter] = useState("");
  if (runs.isPending || definitions.isPending) return <Loading />;
  if (runs.error || definitions.error)
    return <ErrorMessage error={runs.error || definitions.error} />;
  const workflowKeys = Object.fromEntries(
    (definitions.data || []).map((item) => [item.id, item.key]),
  );
  const filteredRuns = (runs.data || []).filter(
    (run) => !filter || run.workflow_definition_id === filter,
  );
  return (
    <>
      <PageTitle
        eyebrow="Your activity"
        title="Activity"
        description="See the notes, plans, and project work you have created with Relay."
      />
      <section className="history-toolbar mb-6 flex justify-end">
        <label className="field min-w-64">
          Type
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="">All work</option>
            {definitions.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {displayFor(item.key)?.title || item.name}
              </option>
            ))}
          </select>
        </label>
      </section>
      <RunList detailed runs={filteredRuns} workflowKeys={workflowKeys} />
    </>
  );
}
