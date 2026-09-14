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
  const filteredRuns = (runs.data || []).filter(
    (run) => !filter || run.workflow_definition_id === filter,
  );
  const activeCount = filteredRuns.filter(
    (run) => !["COMPLETED", "FAILED", "CANCELLED"].includes(run.status),
  ).length;
  return (
    <>
      <PageTitle
        eyebrow="Your activity"
        title="Relays"
        description="Every draft has a place. Review your recent runs and see where things stand."
      />
      <section className="history-toolbar mb-6 grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="system-label">Showing</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">
              {filteredRuns.length}
            </p>
          </div>
          <div>
            <p className="system-label">Active</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">
              {activeCount}
            </p>
          </div>
          <div>
            <p className="system-label">Stored</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">
              {(runs.data || []).length}
            </p>
          </div>
        </div>
        <label className="field min-w-64">
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
      </section>
      <RunList detailed runs={filteredRuns} names={names} />
      <p className="mt-4 text-xs text-muted">Showing up to 50 recent runs.</p>
    </>
  );
}
