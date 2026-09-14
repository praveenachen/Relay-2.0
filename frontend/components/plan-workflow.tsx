"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Database,
  Lock,
  Play,
  Plus,
  RotateCcw,
  Send,
  Trash2,
  Unlock,
  X,
} from "lucide-react";
import { connections } from "@/features/connections/api";
import { preferences } from "@/features/preferences/api";
import { useConnections, usePreferences } from "@/hooks/queries";
import {
  AcademicTask,
  PlanDetail,
  StudySession,
  plan,
} from "@/features/plan/api";
import { WorkflowBadge } from "@/components/workflow-badge";
import { CompletionActions } from "@/components/completion-actions";
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

function localDateValue(iso: string): string {
  return localInputValue(iso).slice(0, 10);
}

function combineLocalDateTime(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString();
}

function defaultWindow(): { startDate: string; endDate: string } {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return {
    startDate: localDateValue(start.toISOString()),
    endDate: localDateValue(end.toISOString()),
  };
}

function prioritizeTasks(tasks: AcademicTask[]): AcademicTask[] {
  return tasks.map((task, index) => ({
    ...task,
    priority: Math.min(index + 1, 5),
  }));
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
        description="Enter your study tasks, and Relay reads your Google Calendar availability, then a deterministic CP-SAT solver -- never a language model -- decides the actual times you study."
        action={<WorkflowBadge workflow={workflowDisplay.study_scheduler} />}
      />
      <RelayLine
        tone="plan"
        sources={[{ label: "Your tasks" }, { label: "Calendar" }]}
        destinations={[
          { label: "Google Calendar" },
          { label: "Notion (optional)" },
        ]}
        status="DRAFT"
      />
      <section className="panel plan-intro my-6">
        <h2 className="section-title">What Relay will do</h2>
        <ol className="learn-steps">
          <li>Collect your study tasks, entered directly in Relay.</li>
          <li>Read the selected Google Calendar and avoid existing events.</li>
          <li>
            Generate a balanced schedule across available days, weighted by
            deadlines, priority, study hours, and breaks.
          </li>
          <li>
            Let you lock, remove, or regenerate sessions before approving.
          </li>
          <li>Create only the approved study blocks on your calendar.</li>
          <li>Optionally export your task list to a new Notion database.</li>
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
        description="Review your tasks, calendar availability, generated schedule, and final calendar publish action for this PLAN workflow."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
        tone="plan"
        sources={[{ label: "Your tasks" }, { label: "Calendar" }]}
        destinations={[
          { label: "Google Calendar" },
          { label: "Notion (optional)" },
        ]}
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
  taskCount: number,
  hasGoogle: boolean,
  calendarId: string,
) {
  if (busy) {
    return {
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
    };
  }
  if (!stage || stage === "setup") {
    if (!hasGoogle) {
      return {
        title: "Next: connect Google Calendar.",
        description:
          "Relay needs a calendar to schedule into before it can build a plan.",
      };
    }
    if (!calendarId) {
      return {
        title: "Next: choose a calendar.",
        description:
          "Select the calendar Relay should schedule study blocks into.",
      };
    }
    return {
      title: "Next: generate your study plan.",
      description: taskCount
        ? "Save your tasks and planning window, then generate the schedule."
        : "Add at least one task, then generate the schedule.",
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
  canPublish: boolean,
) {
  if (busy) {
    return {
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
    };
  }
  if (
    data.run.status === "COMPLETED" ||
    data.run.status === "PARTIALLY_COMPLETED"
  ) {
    return {
      title: "Workflow complete.",
      description:
        "Your approved study blocks have been published. You can export the task list to Notion if you want a separate database copy.",
    };
  }
  if (
    ["PLAN_READY", "AWAITING_APPROVAL", "APPROVED"].includes(data.run.status)
  ) {
    return {
      title: canPublish
        ? "Next: approve and create calendar blocks."
        : "Next: choose where Relay should publish this schedule.",
      description: canPublish
        ? "Review the sessions below, then Relay will approve the exact plan and write those blocks to Google Calendar in one step."
        : "This schedule is locked in, but it needs a Google Calendar destination before publishing.",
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
  const cache = useQueryClient();
  const connectionsQuery = useConnections();
  const preferencesQuery = usePreferences();
  const initialWindow = defaultWindow();
  const [startDate, setStartDate] = useState(
    setup ? localDateValue(setup.window.start) : initialWindow.startDate,
  );
  const [endDate, setEndDate] = useState(
    setup ? localDateValue(setup.window.end) : initialWindow.endDate,
  );
  const [studyStartTime, setStudyStartTime] = useState(
    preferencesQuery.data?.earliest_study_time.slice(0, 5) || "08:00",
  );
  const [studyEndTime, setStudyEndTime] = useState(
    preferencesQuery.data?.latest_study_time.slice(0, 5) || "22:00",
  );
  const [calendarId, setCalendarId] = useState(setup?.calendar_id || "");
  const [editingSetup, setEditingSetup] = useState(!setup);
  const [tasks, setTasks] = useState<AcademicTask[]>(setup?.tasks || []);

  const hasGoogle = (connectionsQuery.data || []).some(
    (item) => item.provider === "GOOGLE" && item.status === "CONNECTED",
  );
  const googleCalendars = useQuery({
    queryKey: ["connections", "google-calendars"],
    queryFn: connections.googleCalendars,
    enabled: hasGoogle,
  });

  const selectedCalendarId =
    calendarId ||
    (googleCalendars.data?.length === 1 ? googleCalendars.data[0].id : "");

  const planSetupPayload = () => ({
    start: combineLocalDateTime(startDate, studyStartTime),
    end: combineLocalDateTime(endDate, studyEndTime),
    calendar_id: selectedCalendarId || null,
    tasks: prioritizeTasks(tasks),
  });

  const generatePlan = useMutation({
    mutationFn: async () => {
      if (preferencesQuery.data) {
        await preferences.save({
          ...preferencesQuery.data,
          earliest_study_time: studyStartTime,
          latest_study_time: studyEndTime,
        });
      }
      return plan.generate(id, planSetupPayload());
    },
    onSuccess: async () => {
      setEditingSetup(false);
      await invalidate();
      await cache.invalidateQueries({ queryKey: ["preferences"] });
    },
    onError: invalidate,
  });
  const loadAvailability = useMutation({
    mutationFn: () => plan.loadAvailability(id),
    onSuccess: invalidate,
  });
  const solve = useMutation({
    mutationFn: () => plan.solve(id),
    onSuccess: invalidate,
  });
  const refreshCalendars = useMutation({
    mutationFn: connections.refreshGoogleCalendars,
    onSuccess: async () => {
      await cache.invalidateQueries({
        queryKey: ["connections", "google-calendars"],
      });
    },
  });

  const busy =
    generatePlan.isPending ||
    loadAvailability.isPending ||
    solve.isPending ||
    refreshCalendars.isPending;
  const stage = setup?.stage;
  const setupError =
    generatePlan.error || loadAvailability.error || solve.error;
  const calendarError = hasGoogle
    ? refreshCalendars.error || googleCalendars.error
    : null;
  const needsTaskSource = tasks.length === 0;
  const needsCalendar = !selectedCalendarId;

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice
        {...planSetupNextStep(
          stage,
          busy,
          tasks.length,
          hasGoogle,
          selectedCalendarId,
        )}
      />
      <ErrorMessage error={setupError} />
      {editingSetup ? (
        <div className="panel">
          <div className="section-heading">
            <h2 className="section-title">Planning window &amp; sources</h2>
            <Link className="text-link text-sm" href="/settings">
              Study preferences
            </Link>
          </div>
          <p className="text-sm text-muted">
            Choose the date range for this plan, then set the daily study-hour
            window Relay should use when scheduling.
          </p>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <label className="field">
              Start date
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>
            <label className="field">
              End date
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </label>
            <label className="field">
              Preferred study start time
              <input
                type="time"
                value={studyStartTime}
                onChange={(event) => setStudyStartTime(event.target.value)}
              />
            </label>
            <label className="field">
              Preferred study end time
              <input
                type="time"
                value={studyEndTime}
                onChange={(event) => setStudyEndTime(event.target.value)}
              />
            </label>
          </div>
          <div className="mt-5 field">
            <div className="destination-picker-heading">
              <span className="field-label">Calendar Relay schedules into</span>
              {hasGoogle && (
                <button
                  className="icon-button"
                  disabled={busy}
                  onClick={() => refreshCalendars.mutate()}
                  aria-label="Refresh Google calendars"
                  title="Refresh Google calendars"
                  type="button"
                >
                  <RotateCcw aria-hidden="true" />
                </button>
              )}
            </div>
            {hasGoogle ? (
              <>
                <select
                  value={selectedCalendarId}
                  onChange={(event) => setCalendarId(event.target.value)}
                >
                  <option value="" disabled>
                    Select a calendar
                  </option>
                  {(googleCalendars.data || []).map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.summary}
                    </option>
                  ))}
                </select>
                <p className="text-sm text-muted">
                  {googleCalendars.isFetching || refreshCalendars.isPending
                    ? "Loading calendars from your connected Google account..."
                    : (googleCalendars.data || []).length === 0
                      ? "Your Google account is connected, but Relay has no calendar list yet. Refresh calendars, then choose where study blocks should go."
                      : "Your Google account is connected. Choose the specific calendar for this plan."}
                </p>
                <ErrorMessage error={calendarError} />
              </>
            ) : (
              <span className="text-sm text-muted">
                <Link className="text-link" href="/connections">
                  Connect Google Calendar
                </Link>{" "}
                to choose a calendar. Relay needs one to schedule study blocks.
              </span>
            )}
          </div>
          <div className="mt-6 border-t border-line pt-5">
            <TaskTable tasks={tasks} onChange={setTasks} editable />
          </div>
          <button
            className="button mt-6"
            disabled={busy || needsTaskSource || needsCalendar}
            onClick={() => generatePlan.mutate()}
          >
            {generatePlan.isPending ? "Generating..." : "Generate study plan"}
          </button>
        </div>
      ) : null}

      {!editingSetup && stage === "setup" && (
        <div className="panel">
          <div className="section-heading">
            <h2 className="section-title">Plan setup saved</h2>
            <button
              type="button"
              className="text-link text-sm"
              onClick={() => setEditingSetup(true)}
            >
              Edit setup
            </button>
          </div>
          <p className="text-sm text-muted">
            Generate the study plan when the planning window, calendar, and task
            source look right.
          </p>
          <button
            className="button mt-5"
            disabled={busy}
            onClick={() => generatePlan.mutate()}
          >
            {generatePlan.isPending ? "Generating..." : "Generate study plan"}
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
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const update = (index: number, patch: Partial<AcademicTask>) =>
    onChange(
      prioritizeTasks(
        tasks.map((task, i) => (i === index ? { ...task, ...patch } : task)),
      ),
    );
  const reorder = (from: number, to: number) => {
    if (
      from === to ||
      from < 0 ||
      to < 0 ||
      from >= tasks.length ||
      to >= tasks.length
    )
      return;
    const next = [...tasks];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    onChange(prioritizeTasks(next));
  };
  const move = (index: number, direction: -1 | 1) =>
    reorder(index, index + direction);
  return (
    <div>
      <div className="section-heading">
        <h3 className="section-title">Tasks</h3>
        {editable && (
          <button
            className="button secondary"
            onClick={() => onChange(prioritizeTasks([...tasks, emptyTask()]))}
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
            <article
              key={task.id}
              className="learn-card"
              draggable={editable}
              onDragStart={() => setDragIndex(index)}
              onDragOver={(event) => editable && event.preventDefault()}
              onDrop={() => {
                if (dragIndex !== null) reorder(dragIndex, index);
                setDragIndex(null);
              }}
              onDragEnd={() => setDragIndex(null)}
            >
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
                  Category (optional)
                  <input
                    disabled={!editable}
                    value={task.course || ""}
                    placeholder="Work, Personal, School..."
                    list={`category-options-${task.id}`}
                    onChange={(e) =>
                      update(index, { course: e.target.value || null })
                    }
                  />
                  <datalist id={`category-options-${task.id}`}>
                    <option value="Work" />
                    <option value="Personal" />
                    <option value="School" />
                    <option value="Other" />
                  </datalist>
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
                    value={
                      task.estimated_minutes === 0 ? "" : task.estimated_minutes
                    }
                    onChange={(e) =>
                      update(index, {
                        estimated_minutes:
                          e.target.value === ""
                            ? 0
                            : Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
              </div>
              {editable && (
                <div className="task-card-actions">
                  <div className="task-priority-controls">
                    <span className="text-sm text-muted">
                      Priority: drag tasks or move them higher/lower
                    </span>
                    <button
                      aria-label={`Move ${task.title || "task"} up`}
                      className="button secondary compact-action"
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp aria-hidden="true" />
                      Higher
                    </button>
                    <button
                      aria-label={`Move ${task.title || "task"} down`}
                      className="button secondary compact-action"
                      disabled={index === tasks.length - 1}
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown aria-hidden="true" />
                      Lower
                    </button>
                  </div>
                  <button
                    aria-label={`Remove ${task.title || "task"}`}
                    className="button secondary compact-action"
                    onClick={() =>
                      onChange(
                        prioritizeTasks(tasks.filter((_, i) => i !== index)),
                      )
                    }
                  >
                    <Trash2 aria-hidden="true" />
                    Remove
                  </button>
                </div>
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
  const publish = useMutation({
    mutationFn: () => plan.approveAndExecute(id),
    onSuccess: invalidate,
  });

  const busy =
    solve.isPending || lock.isPending || remove.isPending || publish.isPending;

  const isCompletePhase =
    data.run.status === "COMPLETED" ||
    data.run.status === "PARTIALLY_COMPLETED";
  const isReviewPhase = !isCompletePhase;
  const canRegenerate = data.run.status === "PLAN_READY";
  const missingCalendar = !setup?.calendar_id;
  const canPublish =
    ["PLAN_READY", "AWAITING_APPROVAL", "APPROVED"].includes(data.run.status) &&
    !!result &&
    result.status !== "INFEASIBLE" &&
    result.sessions.length > 0 &&
    !missingCalendar;

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice {...planReviewNextStep(data, busy, canPublish)} />
      <ErrorMessage
        error={solve.error || lock.error || remove.error || publish.error}
      />

      {isReviewPhase &&
        (result ? (
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
        ))}

      {isReviewPhase && (canRegenerate || canPublish || missingCalendar) && (
        <div className="panel plan-action-panel">
          {missingCalendar ? (
            <div className="blocked-action-card">
              <div>
                <p className="font-medium">
                  Choose a Google Calendar to continue.
                </p>
                <p className="mt-1 text-sm text-muted">
                  This schedule is generated, but Relay needs a calendar
                  destination before it can create study blocks. Connect Google
                  Calendar, then start a new plan and select that calendar in
                  setup.
                </p>
              </div>
              <div className="blocked-action-buttons">
                <Link className="button" href="/connections">
                  Connect Google Calendar
                </Link>
                <Link className="button secondary" href="/workflows/plan">
                  Start new plan
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div className="section-heading">
                <div>
                  <h2 className="section-title">Finalize schedule</h2>
                  <p className="text-sm text-muted">
                    One click approves this exact schedule and creates the study
                    blocks on Google Calendar.
                  </p>
                </div>
                {data.approval && <Status value={data.approval.status} />}
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                {canRegenerate && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => solve.mutate()}
                  >
                    <RotateCcw aria-hidden="true" />
                    Regenerate remaining sessions
                  </button>
                )}
                <button
                  className={
                    canPublish && !busy ? "button" : "button secondary"
                  }
                  disabled={busy || !canPublish}
                  onClick={() => publish.mutate()}
                >
                  <Send aria-hidden="true" />
                  {publish.isPending
                    ? "Creating calendar blocks..."
                    : "Approve and create calendar blocks"}
                </button>
              </div>
            </>
          )}
          {!missingCalendar &&
            !canPublish &&
            result?.status === "INFEASIBLE" && (
              <p className="mt-3 text-sm text-muted">
                This plan is not feasible yet -- adjust the window, preferences,
                or task load before publishing.
              </p>
            )}
        </div>
      )}

      {isCompletePhase && (
        <>
          {(setup?.tasks.length || 0) > 0 && (
            <NotionExportPanel id={id} data={data} invalidate={invalidate} />
          )}
          <ExecutionSummary data={data} />
        </>
      )}
    </section>
  );
}

function ExecutionSummary({ data }: { data: PlanDetail }) {
  const payload = data.run.result_payload as {
    execution?: {
      result?: { created?: { event?: { external_url?: string } }[] };
    };
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
      <CompletionActions
        workflow="plan"
        destinations={[
          data.setup?.notion_export?.database_url,
          ...(payload?.execution?.result?.created || []).map(
            (item) => item.event?.external_url,
          ),
        ]}
      />
    </div>
  );
}

function NotionExportPanel({
  id,
  data,
  invalidate,
}: {
  id: string;
  data: PlanDetail;
  invalidate: () => Promise<void>;
}) {
  const cache = useQueryClient();
  const connectionsQuery = useConnections();
  const hasNotion = (connectionsQuery.data || []).some(
    (item) => item.provider === "NOTION" && item.status === "CONNECTED",
  );
  const [destinationId, setDestinationId] = useState("");
  const destinations = useQuery({
    queryKey: ["connections", "notion-destinations"],
    queryFn: connections.notionDestinations,
    enabled: hasNotion,
  });
  const refreshDestinations = useMutation({
    mutationFn: connections.refreshNotionDestinations,
    onSuccess: (items) => {
      cache.setQueryData(["connections", "notion-destinations"], items);
    },
  });
  const exportToNotion = useMutation({
    mutationFn: () => plan.exportToNotion(id, destinationId),
    onSuccess: invalidate,
  });

  const notionExport = data.setup?.notion_export;
  const busy = refreshDestinations.isPending || exportToNotion.isPending;

  return (
    <div className="panel">
      <div className="section-heading">
        <h2 className="section-title">Export to Notion</h2>
        <Database aria-hidden="true" />
      </div>
      {notionExport && (
        <p className="text-sm text-muted">
          Last exported {notionExport.task_count} task
          {notionExport.task_count === 1 ? "" : "s"} to{" "}
          <a
            className="text-link"
            href={notionExport.database_url}
            target="_blank"
            rel="noreferrer"
          >
            this Notion database
          </a>
          .
        </p>
      )}
      {!hasNotion ? (
        <p className="mt-3 text-sm text-muted">
          <Link className="text-link" href="/connections">
            Connect Notion
          </Link>{" "}
          to export your task list there.
        </p>
      ) : (
        <>
          <div className="mt-4 task-source-picker">
            <div className="destination-picker-heading">
              <span className="field-label">
                Notion page to create the database under
              </span>
              <button
                className="icon-button"
                disabled={busy}
                onClick={() => refreshDestinations.mutate()}
                aria-label="Refresh Notion pages"
                title="Refresh Notion pages"
                type="button"
              >
                <RotateCcw aria-hidden="true" />
              </button>
            </div>
            <select
              value={destinationId}
              onChange={(event) => setDestinationId(event.target.value)}
            >
              <option value="">Select a Notion page</option>
              {(destinations.data || []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
            <p className="text-sm text-muted">
              {destinations.isFetching || refreshDestinations.isPending
                ? "Loading Notion pages..."
                : (destinations.data || []).length === 0
                  ? "No pages found. Refresh after sharing a page with the Relay Notion integration."
                  : "Relay creates a new database under this page and adds one row per task."}
            </p>
          </div>
          <ErrorMessage
            error={
              refreshDestinations.error ||
              destinations.error ||
              exportToNotion.error
            }
          />
          <button
            className="button mt-5"
            disabled={busy || !destinationId}
            onClick={() => exportToNotion.mutate()}
          >
            <Send aria-hidden="true" />
            {exportToNotion.isPending
              ? "Exporting..."
              : notionExport
                ? "Export again"
                : "Export to Notion"}
          </button>
        </>
      )}
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
                  className={`session-card flex flex-wrap items-center justify-between gap-3 rounded-md border border-line px-4 py-3 ${session.locked ? "locked" : ""}`}
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
                        className={
                          session.locked ? "button" : "button secondary"
                        }
                        disabled={busy}
                        aria-pressed={session.locked}
                        aria-label={
                          session.locked
                            ? "Locked -- click to unlock this session"
                            : "Click to lock this session in place"
                        }
                        title={
                          session.locked
                            ? "Locked in place -- click to unlock"
                            : "Click to lock this session in place"
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
                        {session.locked ? "Locked" : "Lock"}
                      </button>
                      <button
                        className="button secondary"
                        disabled={busy}
                        aria-label="Remove session"
                        title="Remove this session"
                        onClick={() => onRemove(session.id as string)}
                      >
                        <Trash2 aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  {(!editable || !session.id) && session.locked && (
                    <span className="context-tag locked">Locked</span>
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
