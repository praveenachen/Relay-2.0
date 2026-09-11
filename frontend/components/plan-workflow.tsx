"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Lock,
  Play,
  Plus,
  RotateCcw,
  Send,
  Trash2,
  Unlock,
  X,
} from "lucide-react";
import { approvals } from "@/features/approvals/api";
import { connections } from "@/features/connections/api";
import { useConnections } from "@/hooks/queries";
import {
  AcademicTask,
  PlanDetail,
  StudySession,
  plan,
} from "@/features/plan/api";
import { WorkflowBadge } from "@/components/workflow-badge";
import { RelayLine } from "@/components/relay-line";
import {
  Empty,
  ErrorMessage,
  Loading,
  PageTitle,
  Status,
} from "@/components/ui";
import { workflowDisplay } from "@/features/workflows/display";

function localInputValue(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function defaultWindow(): { start: string; end: string } {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return {
    start: localInputValue(start.toISOString()),
    end: localInputValue(end.toISOString()),
  };
}

function emptyTask(): AcademicTask {
  const deadline = new Date();
  deadline.setDate(deadline.getDate() + 7);
  return {
    id: `task-${Math.random().toString(36).slice(2, 9)}`,
    title: "",
    course: "",
    deadline: deadline.toISOString(),
    estimated_minutes: 60,
    priority: 3,
    status: "todo",
  };
}

export function PlanEntry() {
  const router = useRouter();
  const create = useMutation({
    mutationFn: plan.create,
    onSuccess: (run) => router.push(`/workflows/plan/${run.id}`),
  });
  return (
    <>
      <PageTitle
        eyebrow="PLAN"
        title="Build a realistic study schedule."
        description="Relay reads your Notion tasks and Google Calendar availability, then a deterministic CP-SAT solver -- never a language model -- decides the actual times you study."
        action={<WorkflowBadge workflow={workflowDisplay.study_scheduler} />}
      />
      <RelayLine
        sources={[{ label: "Notion tasks" }, { label: "Calendar" }]}
        destinations={[{ label: "Google Calendar" }]}
        status="DRAFT"
      />
      <section className="panel my-8">
        <h2 className="section-title">What Relay will do</h2>
        <ol className="learn-steps">
          <li>Import tasks from a Notion database, or enter them directly.</li>
          <li>
            Read your Google Calendar availability for the planning window.
          </li>
          <li>
            Run a CP-SAT solver to place study sessions around real deadlines,
            study hours, and breaks.
          </li>
          <li>Let you lock, move, or remove sessions before approving.</li>
          <li>Create only the approved study blocks on your calendar.</li>
        </ol>
        <button
          className="button mt-6"
          disabled={create.isPending}
          onClick={() => create.mutate()}
        >
          <Play aria-hidden="true" />
          {create.isPending ? "Starting..." : "Start a study plan"}
        </button>
        <ErrorMessage error={create.error} />
      </section>
    </>
  );
}

export function PlanRun({ id }: { id: string }) {
  const cache = useQueryClient();
  const detail = useQuery({
    queryKey: ["plan", id],
    queryFn: () => plan.detail(id),
  });
  const invalidate = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ["plan", id] }),
      cache.invalidateQueries({ queryKey: ["runs"] }),
      cache.invalidateQueries({ queryKey: ["events", id] }),
      cache.invalidateQueries({ queryKey: ["approvals"] }),
    ]);
  };
  if (detail.isPending) return <Loading />;
  if (detail.error) return <ErrorMessage error={detail.error} />;
  const data = detail.data;
  const taskCount = data.setup?.tasks.length || 0;

  return (
    <>
      <PageTitle
        eyebrow="PLAN run"
        title={
          taskCount
            ? `Study plan for ${taskCount} task${taskCount === 1 ? "" : "s"}`
            : "Study plan"
        }
        description="Review the imported tasks, calendar availability, generated schedule, and approval for this PLAN workflow."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
        sources={[{ label: "Notion tasks" }, { label: "Calendar" }]}
        destinations={[{ label: "Google Calendar" }]}
        status={data.run.status}
      />
      {data.run.error_message && (
        <div className="notice error my-6">
          <X aria-hidden="true" />
          <p>{data.run.error_message}</p>
        </div>
      )}
      {data.run.status === "DRAFT" ? (
        <SetupWizard id={id} data={data} invalidate={invalidate} />
      ) : (
        <ReviewAndApprove id={id} data={data} invalidate={invalidate} />
      )}
    </>
  );
}

function planSetupNextStep(
  stage: string | undefined,
  busy: boolean,
  databaseId: string,
  taskCount: number,
) {
  if (busy) {
    return {
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
    };
  }
  if (!stage || stage === "setup") {
    return {
      title: "Next: save your planning setup.",
      description: databaseId
        ? "Relay will use the selected Notion database after you save this setup."
        : taskCount
          ? "Save the manually entered tasks and planning window to continue."
          : "Add at least one task, or choose a Notion task database, then save the setup.",
    };
  }
  if (stage === "tasks_imported") {
    return {
      title: "Next: review tasks and load availability.",
      description:
        "Check deadlines and estimates, save edits if needed, then continue to calendar availability.",
    };
  }
  if (stage === "availability_loaded") {
    return {
      title: "Next: generate the study plan.",
      description:
        "Relay will run the scheduler against tasks, deadlines, preferences, and calendar availability.",
    };
  }
  return {
    title: "Next: continue the plan setup.",
    description: "Complete the active setup section below.",
  };
}

function planReviewNextStep(
  data: PlanDetail,
  busy: boolean,
  canRequestApproval: boolean,
) {
  if (busy) {
    return {
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
    };
  }
  if (data.run.status === "PLAN_READY") {
    return {
      title: canRequestApproval
        ? "Next: request approval for this schedule."
        : "Next: adjust this schedule before approval.",
      description: canRequestApproval
        ? "Review the sessions below, then request approval when the calendar blocks look right."
        : "This schedule cannot be approved yet. Adjust the task load, planning window, or preferences.",
    };
  }
  if (data.approval?.status === "PENDING") {
    return {
      title: "Next: approve or reject the plan.",
      description:
        "Approval is the final checkpoint before Relay writes to Google Calendar.",
    };
  }
  if (data.run.status === "APPROVED") {
    return {
      title: "Next: publish the approved schedule.",
      description: "Create the approved study blocks on Google Calendar.",
    };
  }
  return {
    title: "Workflow status updated.",
    description:
      "Relay will show the next available action as the plan progresses.",
  };
}

function NextStepNotice({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const working = title.startsWith("Relay is working");
  return (
    <div className={`notice next-step my-6 ${working ? "working" : ""}`}>
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1">{description}</p>
      </div>
    </div>
  );
}

function SetupWizard({
  id,
  data,
  invalidate,
}: {
  id: string;
  data: PlanDetail;
  invalidate: () => Promise<void>;
}) {
  const setup = data.setup;
  const connectionsQuery = useConnections();
  const googleCalendars = useQuery({
    queryKey: ["connections", "google-calendars"],
    queryFn: connections.googleCalendars,
  });
  const notionDatabases = useQuery({
    queryKey: ["connections", "notion-task-databases"],
    queryFn: connections.notionTaskDatabases,
  });
  const initialWindow = defaultWindow();
  const [start, setStart] = useState(
    setup ? localInputValue(setup.window.start) : initialWindow.start,
  );
  const [end, setEnd] = useState(
    setup ? localInputValue(setup.window.end) : initialWindow.end,
  );
  const [calendarId, setCalendarId] = useState(setup?.calendar_id || "");
  const [databaseId, setDatabaseId] = useState(setup?.notion_database_id || "");
  const [mappingTitle, setMappingTitle] = useState(
    setup?.notion_mapping?.title || "Task Name",
  );
  const [mappingCourse, setMappingCourse] = useState(
    setup?.notion_mapping?.course || "",
  );
  const [mappingDeadline, setMappingDeadline] = useState(
    setup?.notion_mapping?.deadline || "Due Date",
  );
  const [mappingEstimate, setMappingEstimate] = useState(
    setup?.notion_mapping?.estimated_minutes || "Estimated Hours",
  );
  const [mappingUnit, setMappingUnit] = useState<"minutes" | "hours">(
    setup?.notion_mapping?.estimate_unit || "hours",
  );
  const [mappingPriority, setMappingPriority] = useState(
    setup?.notion_mapping?.priority || "",
  );
  const [mappingStatus, setMappingStatus] = useState(
    setup?.notion_mapping?.status || "Status",
  );
  const [tasks, setTasks] = useState<AcademicTask[]>(setup?.tasks || []);

  const hasGoogle = (connectionsQuery.data || []).some(
    (item) => item.provider === "GOOGLE" && item.status === "CONNECTED",
  );
  const hasNotion = (connectionsQuery.data || []).some(
    (item) => item.provider === "NOTION" && item.status === "CONNECTED",
  );

  const buildMapping = () => ({
    title: mappingTitle,
    course: mappingCourse || null,
    deadline: mappingDeadline,
    priority: mappingPriority || null,
    estimated_minutes: mappingEstimate,
    status: mappingStatus || null,
    estimate_unit: mappingUnit,
  });

  const saveSetup = useMutation({
    mutationFn: (overrides: { detachNotion?: boolean } = {}) =>
      plan.setup(id, {
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
        calendar_id: calendarId || null,
        notion_database_id: overrides.detachNotion ? null : databaseId || null,
        notion_mapping:
          overrides.detachNotion || !databaseId ? null : buildMapping(),
        tasks,
      }),
    onSuccess: invalidate,
  });
  const importTasks = useMutation({
    mutationFn: () => plan.importTasks(id),
    onSuccess: invalidate,
  });
  const loadAvailability = useMutation({
    mutationFn: () => plan.loadAvailability(id),
    onSuccess: invalidate,
  });
  const solve = useMutation({
    mutationFn: () => plan.solve(id),
    onSuccess: invalidate,
  });

  const busy =
    saveSetup.isPending ||
    importTasks.isPending ||
    loadAvailability.isPending ||
    solve.isPending;
  const stage = setup?.stage;

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice
        {...planSetupNextStep(stage, busy, databaseId, tasks.length)}
      />
      <ErrorMessage
        error={
          saveSetup.error ||
          importTasks.error ||
          loadAvailability.error ||
          solve.error
        }
      />
      {!stage || stage === "setup" ? (
        <div className="panel">
          <div className="section-heading">
            <h2 className="section-title">Planning window &amp; sources</h2>
            <Link className="text-link text-sm" href="/settings">
              Study preferences
            </Link>
          </div>
          <p className="text-sm text-muted">
            Relay schedules within your study hours, session lengths, and break
            preferences from Settings.
          </p>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <label className="field">
              Start
              <input
                type="datetime-local"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label className="field">
              End
              <input
                type="datetime-local"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </label>
          </div>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <label className="field">
              Calendar Relay schedules into
              {hasGoogle ? (
                <select
                  value={calendarId}
                  onChange={(event) => setCalendarId(event.target.value)}
                >
                  <option value="">Use default calendar</option>
                  {(googleCalendars.data || []).map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.summary}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-sm text-muted">
                  <Link className="text-link" href="/connections">
                    Connect Google Calendar
                  </Link>{" "}
                  to choose a calendar.
                </span>
              )}
            </label>
            <label className="field">
              Notion task database (optional)
              {hasNotion ? (
                <select
                  value={databaseId}
                  onChange={(event) => setDatabaseId(event.target.value)}
                >
                  <option value="">Enter tasks manually</option>
                  {(notionDatabases.data || []).map((database) => (
                    <option key={database.id} value={database.id}>
                      {database.title}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-sm text-muted">
                  <Link className="text-link" href="/connections">
                    Connect Notion
                  </Link>{" "}
                  to import tasks, or enter them manually below.
                </span>
              )}
            </label>
          </div>
          {databaseId && (
            <div className="mt-6 border-t border-line pt-5">
              <h3 className="section-title">Notion property mapping</h3>
              <p className="text-sm text-muted">
                Match Relay&apos;s task fields to this database&apos;s property
                names. Relay never guesses a missing estimate or deadline.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <label className="field">
                  Title property
                  <input
                    value={mappingTitle}
                    onChange={(e) => setMappingTitle(e.target.value)}
                  />
                </label>
                <label className="field">
                  Course property
                  <input
                    value={mappingCourse}
                    onChange={(e) => setMappingCourse(e.target.value)}
                  />
                </label>
                <label className="field">
                  Status property
                  <input
                    value={mappingStatus}
                    onChange={(e) => setMappingStatus(e.target.value)}
                  />
                </label>
                <label className="field">
                  Deadline property
                  <input
                    value={mappingDeadline}
                    onChange={(e) => setMappingDeadline(e.target.value)}
                  />
                </label>
                <label className="field">
                  Priority property
                  <input
                    value={mappingPriority}
                    onChange={(e) => setMappingPriority(e.target.value)}
                  />
                </label>
                <label className="field">
                  Estimate property
                  <input
                    value={mappingEstimate}
                    onChange={(e) => setMappingEstimate(e.target.value)}
                  />
                </label>
                <label className="field">
                  Estimate unit
                  <select
                    value={mappingUnit}
                    onChange={(e) =>
                      setMappingUnit(e.target.value as "minutes" | "hours")
                    }
                  >
                    <option value="minutes">Minutes</option>
                    <option value="hours">Hours</option>
                  </select>
                </label>
              </div>
            </div>
          )}
          {!databaseId && (
            <div className="mt-6 border-t border-line pt-5">
              <TaskTable tasks={tasks} onChange={setTasks} editable />
            </div>
          )}
          <button
            className="button mt-6"
            disabled={busy || (!databaseId && tasks.length === 0)}
            onClick={() => saveSetup.mutate({})}
          >
            {saveSetup.isPending ? "Saving..." : "Save and continue"}
          </button>
        </div>
      ) : null}

      {stage === "setup" && (
        <div className="panel">
          <h2 className="section-title">Import tasks</h2>
          <p className="text-sm text-muted">
            {setup?.notion_database_id
              ? "Relay will read tasks from the selected Notion database."
              : "Relay will use the tasks you entered."}
          </p>
          <button
            className="button mt-5"
            disabled={busy}
            onClick={() => importTasks.mutate()}
          >
            Import tasks
          </button>
        </div>
      )}

      {stage === "tasks_imported" && setup && (
        <div className="panel">
          <h2 className="section-title">Review imported tasks</h2>
          {setup.task_issues.length > 0 && (
            <div className="notice mb-5">
              <p className="font-medium">
                {setup.task_issues.length} Notion page
                {setup.task_issues.length === 1 ? "" : "s"} could not be
                imported.
              </p>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {setup.task_issues.map((issue, index) => (
                  <li key={index}>{issue.message}</li>
                ))}
              </ul>
            </div>
          )}
          <TaskTable tasks={tasks} onChange={setTasks} editable />
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => saveSetup.mutate({ detachNotion: true })}
            >
              Save edits
            </button>
            <button
              className="button"
              disabled={busy || tasks.length === 0}
              onClick={() => loadAvailability.mutate()}
            >
              Continue to availability
            </button>
          </div>
        </div>
      )}

      {stage === "availability_loaded" && setup && (
        <div className="panel">
          <h2 className="section-title">Calendar availability</h2>
          <p className="text-sm text-muted">
            {setup.calendar_id
              ? `Relay found ${setup.busy_intervals.length} existing event${setup.busy_intervals.length === 1 ? "" : "s"} in the planning window.`
              : "No calendar is selected -- Relay will treat the whole window as free."}
          </p>
          <button
            className="button mt-5"
            disabled={busy}
            onClick={() => solve.mutate()}
          >
            <Play aria-hidden="true" />
            Generate study plan
          </button>
        </div>
      )}
    </section>
  );
}

function TaskTable({
  tasks,
  onChange,
  editable,
}: {
  tasks: AcademicTask[];
  onChange: (tasks: AcademicTask[]) => void;
  editable: boolean;
}) {
  const update = (index: number, patch: Partial<AcademicTask>) =>
    onChange(
      tasks.map((task, i) => (i === index ? { ...task, ...patch } : task)),
    );
  return (
    <div>
      <div className="section-heading">
        <h3 className="section-title">Tasks</h3>
        {editable && (
          <button
            className="button secondary"
            onClick={() => onChange([...tasks, emptyTask()])}
          >
            <Plus aria-hidden="true" />
            Add task
          </button>
        )}
      </div>
      {tasks.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No tasks yet.</p>
      ) : (
        <div className="mt-4 space-y-4">
          {tasks.map((task, index) => (
            <article key={task.id} className="learn-card">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="field">
                  Title
                  <input
                    disabled={!editable}
                    value={task.title}
                    onChange={(e) => update(index, { title: e.target.value })}
                  />
                </label>
                <label className="field">
                  Course
                  <input
                    disabled={!editable}
                    value={task.course || ""}
                    onChange={(e) =>
                      update(index, { course: e.target.value || null })
                    }
                  />
                </label>
                <label className="field">
                  Deadline
                  <input
                    type="datetime-local"
                    disabled={!editable}
                    value={localInputValue(task.deadline)}
                    onChange={(e) =>
                      update(index, {
                        deadline: new Date(e.target.value).toISOString(),
                      })
                    }
                  />
                </label>
                <label className="field">
                  Estimated minutes
                  <input
                    type="number"
                    min={5}
                    disabled={!editable}
                    value={task.estimated_minutes}
                    onChange={(e) =>
                      update(index, {
                        estimated_minutes: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
                <label className="field">
                  Priority (1 urgent - 5 low)
                  <input
                    type="number"
                    min={1}
                    max={5}
                    disabled={!editable}
                    value={task.priority}
                    onChange={(e) =>
                      update(index, { priority: Number(e.target.value) || 3 })
                    }
                  />
                </label>
              </div>
              {editable && (
                <button
                  aria-label={`Remove ${task.title || "task"}`}
                  className="button secondary mt-3"
                  onClick={() => onChange(tasks.filter((_, i) => i !== index))}
                >
                  <Trash2 aria-hidden="true" />
                  Remove
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function ReviewAndApprove({
  id,
  data,
  invalidate,
}: {
  id: string;
  data: PlanDetail;
  invalidate: () => Promise<void>;
}) {
  const setup = data.setup;
  const result = data.result;
  const solve = useMutation({
    mutationFn: () => plan.solve(id),
    onSuccess: invalidate,
  });
  const lock = useMutation({
    mutationFn: ({
      sessionId,
      locked,
    }: {
      sessionId: string;
      locked: boolean;
    }) => plan.lockSession(id, sessionId, locked),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (sessionId: string) => plan.removeSession(id, sessionId),
    onSuccess: invalidate,
  });
  const requestApproval = useMutation({
    mutationFn: () => plan.requestApproval(id),
    onSuccess: invalidate,
  });
  const resolve = useMutation({
    mutationFn: ({ approve }: { approve: boolean }) => {
      const approval = data.approval;
      if (!approval) throw new Error("No approval is available.");
      return approvals.resolve(approval, approve);
    },
    onSuccess: invalidate,
  });
  const execute = useMutation({
    mutationFn: () => plan.execute(id),
    onSuccess: invalidate,
  });

  const busy =
    solve.isPending ||
    lock.isPending ||
    remove.isPending ||
    requestApproval.isPending ||
    resolve.isPending ||
    execute.isPending;

  const canRegenerate = data.run.status === "PLAN_READY";
  const canRequestApproval =
    data.run.status === "PLAN_READY" &&
    !!result &&
    result.status !== "INFEASIBLE" &&
    result.sessions.length > 0;
  const pendingApproval = data.approval?.status === "PENDING";

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice {...planReviewNextStep(data, busy, canRequestApproval)} />
      <ErrorMessage
        error={
          solve.error ||
          lock.error ||
          remove.error ||
          requestApproval.error ||
          resolve.error ||
          execute.error
        }
      />
      {result ? (
        <SchedulePanel
          result={result}
          tasks={setup?.tasks || []}
          editable={canRegenerate}
          busy={busy}
          onLock={(sessionId, locked) => lock.mutate({ sessionId, locked })}
          onRemove={(sessionId) => remove.mutate(sessionId)}
        />
      ) : (
        <Empty title="No schedule generated yet.">
          Generate a study plan from the setup step.
        </Empty>
      )}
      {canRegenerate && (
        <div className="panel">
          <div className="flex flex-wrap gap-3">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => solve.mutate()}
            >
              <RotateCcw aria-hidden="true" />
              Regenerate remaining sessions
            </button>
            <button
              className={
                canRequestApproval && !busy ? "button" : "button secondary"
              }
              disabled={busy || !canRequestApproval}
              onClick={() => requestApproval.mutate()}
            >
              <Send aria-hidden="true" />
              Request approval
            </button>
          </div>
          {!canRequestApproval && result?.status === "INFEASIBLE" && (
            <p className="mt-3 text-sm text-muted">
              This plan is not feasible yet -- adjust the window, preferences,
              or task load before requesting approval.
            </p>
          )}
        </div>
      )}
      {data.approval && (
        <div className="panel">
          <h2 className="section-title">Approval</h2>
          <Status value={data.approval.status} />
          {pendingApproval && (
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="button"
                disabled={busy}
                onClick={() => resolve.mutate({ approve: true })}
              >
                <Check aria-hidden="true" />
                Approve plan
              </button>
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => resolve.mutate({ approve: false })}
              >
                <X aria-hidden="true" />
                Reject
              </button>
            </div>
          )}
          {data.run.status === "APPROVED" && (
            <button
              className="button mt-5"
              disabled={busy}
              onClick={() => execute.mutate()}
            >
              <Send aria-hidden="true" />
              Create approved calendar blocks
            </button>
          )}
        </div>
      )}
      {(data.run.status === "COMPLETED" ||
        data.run.status === "PARTIALLY_COMPLETED") && (
        <ExecutionSummary data={data} />
      )}
    </section>
  );
}

function ExecutionSummary({ data }: { data: PlanDetail }) {
  const payload = data.run.result_payload as {
    created_count?: number;
    failed_count?: number;
    approved_count?: number;
  } | null;
  return (
    <div className="panel">
      <h2 className="section-title">Calendar result</h2>
      <p className="text-sm">
        {payload?.created_count ?? 0} of {payload?.approved_count ?? 0} approved
        study blocks created
        {payload?.failed_count ? `, ${payload.failed_count} failed` : ""}.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link className="button secondary" href="/dashboard">
          Dashboard
        </Link>
        <Link className="button secondary" href="/workflows/plan">
          Start another
        </Link>
      </div>
    </div>
  );
}

function SchedulePanel({
  result,
  tasks,
  editable,
  busy,
  onLock,
  onRemove,
}: {
  result: PlanDetail["result"];
  tasks: AcademicTask[];
  editable: boolean;
  busy: boolean;
  onLock: (sessionId: string, locked: boolean) => void;
  onRemove: (sessionId: string) => void;
}) {
  if (!result) return null;
  const titleFor = (taskId: string) =>
    tasks.find((task) => task.id === taskId)?.title || taskId;
  const courseFor = (taskId: string) =>
    tasks.find((task) => task.id === taskId)?.course;
  const byDay = new Map<string, StudySession[]>();
  for (const session of result.sessions) {
    const day = new Date(session.start).toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
    });
    byDay.set(day, [...(byDay.get(day) || []), session]);
  }
  return (
    <div className="panel">
      <div className="section-heading">
        <h2 className="section-title">Study plan</h2>
        <Status value={result.status} />
      </div>
      <div className="mt-4 grid gap-3 text-sm text-muted md:grid-cols-4">
        <span>
          {result.metrics.tasks_fully_scheduled} task(s) fully scheduled
        </span>
        <span>
          {result.metrics.tasks_partially_scheduled} partially scheduled
        </span>
        <span>{result.metrics.session_count} session(s)</span>
        <span>{result.metrics.unscheduled_minutes} unscheduled minute(s)</span>
      </div>
      {result.conflicts.length > 0 && (
        <div className="notice mt-5">
          <p className="font-medium">Relay could not schedule everything.</p>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {result.conflicts.map((conflict, index) => (
              <li key={index}>
                {titleFor(conflict.task_id || "")}: {conflict.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-6 space-y-6">
        {[...byDay.entries()].map(([day, sessions]) => (
          <div key={day}>
            <h3 className="section-title">{day}</h3>
            <div className="mt-3 space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line px-4 py-3"
                >
                  <div>
                    <p className="font-medium">{titleFor(session.task_id)}</p>
                    <p className="text-sm text-muted">
                      {courseFor(session.task_id)
                        ? `${courseFor(session.task_id)} - `
                        : ""}
                      {new Date(session.start).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                      })}{" "}
                      -{" "}
                      {new Date(session.end).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  {editable && session.id && (
                    <div className="flex gap-2">
                      <button
                        className="button secondary"
                        disabled={busy}
                        aria-label={
                          session.locked ? "Unlock session" : "Lock session"
                        }
                        onClick={() =>
                          onLock(session.id as string, !session.locked)
                        }
                      >
                        {session.locked ? (
                          <Unlock aria-hidden="true" />
                        ) : (
                          <Lock aria-hidden="true" />
                        )}
                      </button>
                      <button
                        className="button secondary"
                        disabled={busy}
                        aria-label="Remove session"
                        onClick={() => onRemove(session.id as string)}
                      >
                        <Trash2 aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  {session.locked && (
                    <span className="context-tag">Locked</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
