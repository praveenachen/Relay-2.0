"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useDefinitions } from "@/hooks/queries";
import { runs as runApi } from "@/features/workflow-runs/api";
import type { WorkflowDisplay } from "@/features/workflows/display";
import { RelayLine } from "@/components/relay-line";
import { WorkflowBadge } from "@/components/workflow-badge";
import { ErrorMessage, Loading, PageTitle } from "@/components/ui";

export function WorkflowEntry({ display }: { display: WorkflowDisplay }) {
  const definitions = useDefinitions();
  const router = useRouter(),
    cache = useQueryClient();
  const create = useMutation({
    mutationFn: runApi.create,
    onSuccess: async (run) => {
      await cache.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/runs/${run.id}`);
    },
  });
  if (definitions.isPending) return <Loading />;
  if (definitions.error) return <ErrorMessage error={definitions.error} />;
  const definition = definitions.data?.find((item) => item.key === display.key);
  return (
    <>
      <PageTitle
        eyebrow={display.pillar}
        title={display.headline}
        description={display.description}
        action={<WorkflowBadge workflow={display} />}
      />
      <RelayLine
        tone={display.tone}
        sources={display.sources.map((label) => ({ label }))}
        destinations={display.destinations.map((label) => ({ label }))}
        status="DRAFT"
      />
      <section className="my-10">
        <h2 className="section-title">What happens next</h2>
        <ol className="grid gap-5 sm:grid-cols-2">
          {display.steps.map((step, index) => (
            <li key={step} className="panel interactive">
              <p className="eyebrow">Step {index + 1}</p>
              <p className="mt-3 text-sm leading-6">{step}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className="mb-10">
        <h2 className="section-title">{display.inputLabel}</h2>
        <div className="panel">
          <label className="field opacity-60">
            {display.inputLabel}
            <textarea
              rows={4}
              disabled
              placeholder="Coming in a future build phase"
            />
          </label>
          <p className="notice mt-5">{display.inputHint}</p>
        </div>
      </section>
      <div className="flex flex-wrap items-center gap-4">
        <button
          className="button"
          disabled={!definition?.enabled || create.isPending}
          onClick={() => definition && create.mutate(definition.id)}
        >
          {!definition?.enabled
            ? "Unavailable"
            : create.isPending
              ? "Creating..."
              : "Create draft"}
        </button>
        <p className="text-sm text-muted">
          You can return and continue whenever you are ready.
        </p>
      </div>
      <ErrorMessage error={create.error} />
    </>
  );
}
