"use client";
import Link from "next/link";
import { useDefinitions, useEvents, useRun } from "@/hooks/queries";
import { RelayLine } from "@/components/relay-line";
import { Empty, ErrorMessage, Loading, PageTitle } from "@/components/ui";
import {
  displayFor,
  friendlyKey,
  runTitle,
} from "@/features/workflows/display";
import { statusFor } from "@/features/workflows/status";

function eventLabel(value: string): string {
  const labels: Record<string, string> = {
    WORKFLOW_RUN_CREATED: "Work started",
    WORKFLOW_CREATED: "Work started",
    WORKFLOW_STATE_CHANGED: "Progress updated",
    DOCUMENT_UPLOADED: "Lecture material uploaded",
    DOCUMENT_PARSED: "Lecture material organized",
    SUMMARY_GENERATED: "Study notes created",
    APPROVAL_REQUESTED: "Ready for review",
    APPROVAL_APPROVED: "Changes confirmed",
    APPROVAL_REJECTED: "Changes declined",
    ACTION_APPROVED: "Changes confirmed",
    ACTION_REJECTED: "Changes declined",
    APPROVAL_EXPIRED: "Review no longer needed",
    PROPOSED_ACTION_CREATED: "Review prepared",
    ACTION_EDITED: "Notes updated",
    ACTION_ITEM_EDITED: "Task updated",
    EXECUTION_STARTED: "Saving started",
    EXECUTION_SUBMITTED: "Ready to save",
    EXTERNAL_EXECUTION_STARTED: "Saving started",
    EXECUTION_COMPLETED: "Saved successfully",
    WORKFLOW_RUN_COMPLETED: "Work completed",
    WORKFLOW_COMPLETED: "Work completed",
    PLAN_SETUP_SAVED: "Plan details saved",
    PLAN_APPROVAL_REQUESTED: "Study plan ready for review",
    SCHEDULING_STARTED: "Building your study plan",
    SESSION_MOVED: "Study session moved",
    NOTION_DESTINATION_SELECTED: "Notion location selected",
    NOTION_PAGE_CREATE_STARTED: "Saving to Notion",
    ANALYSIS_STARTED: "Organizing meeting notes",
    MEETING_ANALYSIS_STARTED: "Finding decisions and tasks",
  };
  return labels[value] || friendlyKey(value);
}

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
  const kind = run.data.input_payload.kind;
  const projectId = run.data.project_workspace_id;
  const workspaceHref =
    projectId && kind === "project_task_github_issue"
      ? `/projects/${projectId}?tab=tasks`
      : projectId && kind === "publish_notion_project"
        ? `/projects/${projectId}`
        : projectId && display?.slug === "plan"
          ? `/projects/${projectId}?tab=plan`
          : definition?.key === "source_to_tasks"
            ? "/inbox"
            : display
              ? `/workflows/${display.slug}/${run.data.id}`
              : undefined;
  return (
    <>
      <PageTitle
        eyebrow={display?.title || "Activity"}
        title={runTitle(run.data, display)}
        description={statusFor(run.data.status).description}
      />
      <RelayLine
        tone={display?.tone}
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
                : `${display?.title || name} is ready to continue.`
            }
            action={
              <Link className="button" href={workspaceHref}>
                Continue {display?.title || name}
              </Link>
            }
          >
            Pick up where you left off and review the next step.
          </Empty>
        ) : (
          <Empty
            title={
              run.data.status === "DRAFT"
                ? "Your draft is saved."
                : "Open this work."
            }
          >
            This work does not have a dedicated editor. Its activity is
            available below.
          </Empty>
        )}
      </div>
      {run.data.status === "AWAITING_APPROVAL" && (
        <Link className="button mb-8" href={workspaceHref || "/approvals"}>
          Review now
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
                  {eventLabel(event.event_type)}
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
                        Saved preview: {event.event_metadata.external_url}
                      </span>
                    ) : (
                      <a
                        className="text-link"
                        href={event.event_metadata.external_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open saved item
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
