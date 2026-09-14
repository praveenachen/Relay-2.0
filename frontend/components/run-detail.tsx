"use client";
import Link from "next/link";
import { useDefinitions, useEvents, useRun } from "@/hooks/queries";
import { RelayLine } from "@/components/relay-line";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";
import { displayFor } from "@/features/workflows/display";

export function RunDetail({ id }: { id: string }) {
  const run = useRun(id),
    events = useEvents(id),
    definitions = useDefinitions();
  if (run.isPending) return <Loading />;
  if (run.error) return <ErrorMessage error={run.error} />;
  const definition = definitions.data?.find(
    (item) => item.id === run.data.workflow_definition_id,
  );
  const display = displayFor(definition?.key);
  const name = definition?.name || "Relay";
  const workspaceHref = display
    ? `/workflows/${display.slug}/${run.data.id}`
    : undefined;
  return (
    <>
      <PageTitle
        eyebrow="Workflow run"
        title={`${name} / ${run.data.status.toLowerCase().replaceAll("_", " ")}`}
        description="A clear record of your intent and every step that follows."
      />
      <RelayLine
        sources={display?.sources.map((label) => ({ label }))}
        destinations={display?.destinations.map((label) => ({ label }))}
        status={run.data.status}
      />
      <div className="my-8">
        {workspaceHref ? (
          <Empty
            title={
              run.data.status === "DRAFT"
                ? "Your draft is saved."
                : `${display?.title || name} processing is available.`
            }
            action={
              <Link className="button" href={workspaceHref}>
                Open {display?.title || name} review
              </Link>
            }
          >
            Continue review, approval, and execution from the dedicated{" "}
            {display?.title || name} workspace.
          </Empty>
        ) : (
          <Empty
            title={
              run.data.status === "DRAFT"
                ? "Your draft is saved."
                : "Open the workflow."
            }
          >
            This run belongs to a workflow that does not have a dedicated
            workspace route in the current UI. Its activity log remains
            available below.
          </Empty>
        )}
      </div>
      {run.data.status === "AWAITING_APPROVAL" && (
        <Link className="button mb-8" href={workspaceHref || "/approvals"}>
          Review approval
        </Link>
      )}
      <section>
        <h2 className="section-title">Activity</h2>
        <ErrorMessage error={events.error} />
        {events.isPending ? (
          <Loading />
        ) : (
          <ol className="space-y-4">
            {events.data?.map((event) => (
              <li className="border-l-2 border-accent pl-5" key={event.id}>
                <p className="text-sm font-medium">
                  {event.event_type.toLowerCase().replaceAll("_", " ")}
                  {event.event_metadata.simulated === true
                    ? " (simulated)"
                    : ""}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {new Date(event.created_at).toLocaleString()}
                </p>
                {typeof event.event_metadata.external_url === "string" && (
                  <p className="mt-1 text-xs">
                    {event.event_metadata.external_url.startsWith("mock://") ? (
                      <span className="text-muted">
                        Simulated artifact: {event.event_metadata.external_url}
                      </span>
                    ) : (
                      <a
                        className="text-link"
                        href={event.event_metadata.external_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open artifact
                      </a>
                    )}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
