"use client";
import Link from "next/link";
import { useDefinitions, useEvents, useRun } from "@/hooks/queries";
import { RelayLine } from "@/components/relay-line";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";
export function RunDetail({ id }: { id: string }) {
  const run = useRun(id),
    events = useEvents(id),
    definitions = useDefinitions();
  if (run.isPending) return <Loading />;
  if (run.error) return <ErrorMessage error={run.error} />;
  const name =
    definitions.data?.find(
      (item) => item.id === run.data.workflow_definition_id,
    )?.name || "Relay";
  const isLearn =
    definitions.data?.find(
      (item) => item.id === run.data.workflow_definition_id,
    )?.key === "lecture_to_notion";
  return (
    <>
      <PageTitle
        eyebrow="Workflow run"
        title={`${name} / ${run.data.status.toLowerCase().replaceAll("_", " ")}`}
        description="A clear record of your intent and every step that follows."
      />
      <RelayLine status={run.data.status} />
      <div className="my-8">
        {isLearn ? (
          <Empty
            title={
              run.data.status === "DRAFT"
                ? "Your draft is saved."
                : "LEARN processing is available."
            }
            action={
              <Link className="button" href={`/workflows/learn/${run.data.id}`}>
                Open LEARN review
              </Link>
            }
          >
            Continue with upload, parsing, summary review, approval, and mock
            publishing from the dedicated LEARN workspace.
          </Empty>
        ) : (
          <Empty
            title={
              run.data.status === "DRAFT"
                ? "Your draft is saved."
                : "Execution is not available yet."
            }
          >
            Workflow automation is planned for a later phase. No content has
            been analyzed and no external action has run from this workspace.
          </Empty>
        )}
      </div>
      {run.data.status === "AWAITING_APPROVAL" && (
        <Link
          className="button mb-8"
          href={isLearn ? `/workflows/learn/${run.data.id}` : "/approvals"}
        >
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
                </p>
                <p className="mt-1 text-xs text-muted">
                  {new Date(event.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
