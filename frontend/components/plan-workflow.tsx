"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Database,
  Keyboard,
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
import { preferences } from "@/features/preferences/api";
import { useConnections, usePreferences } from "@/hooks/queries";
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
  usingNotion: boolean,
  databaseId: string,
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
      title: "Next: save your planning setup.",
      description: usingNotion
        ? databaseId
          ? "Relay will use the selected Notion database after you save this setup."
          : "Choose a Notion task database, then save the setup."
        : taskCount
          ? "Save the manually entered tasks and planning window to continue."
          : "Add at least one manual task, or import tasks from Notion, then save the setup.",
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
  const [taskSource, setTaskSource] = useState<"manual" | "notion">(
    setup?.notion_database_id ? "notion" : "manual",
  );
  const [databaseId, setDatabaseId] = useState(setup?.notion_database_id || "");
  const [editingSetup, setEditingSetup] = useState(!setup);
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
  const googleCalendars = useQuery({
    queryKey: ["connections", "google-calendars"],
    queryFn: connections.googleCalendars,
    enabled: hasGoogle,
  });
  const notionDatabases = useQuery({
    queryKey: ["connections", "notion-task-databases"],
    queryFn: connections.notionTaskDatabases,
    enabled: hasNotion && taskSource === "notion",
  });
  const usingNotion = taskSource === "notion";

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
    mutationFn: async (overrides: { detachNotion?: boolean } = {}) => {
      if (preferencesQuery.data) {
        await preferences.save({
          ...preferencesQuery.data,
          earliest_study_time: studyStartTime,
          latest_study_time: studyEndTime,
        });
      }
      const selectedDatabaseId =
        !overrides.detachNotion && usingNotion ? databaseId || null : null;
      return plan.setup(id, {
        start: combineLocalDateTime(startDate, studyStartTime),
        end: combineLocalDateTime(endDate, studyEndTime),
        calendar_id: calendarId || null,
        notion_database_id: selectedDatabaseId,
        notion_mapping: selectedDatabaseId ? buildMapping() : null,
        tasks: prioritizeTasks(tasks),
      });
    },
    onSuccess: async () => {
      setEditingSetup(false);
      await invalidate();
      await cache.invalidateQueries({ queryKey: ["preferences"] });
    },
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
  const refreshDatabases = useMutation({
    mutationFn: connections.refreshNotionTaskDatabases,
    onSuccess: async () => {
      await cache.invalidateQueries({
        queryKey: ["connections", "notion-task-databases"],
      });
    },
  });

  const busy =
    saveSetup.isPending ||
    importTasks.isPending ||
    loadAvailability.isPending ||
    solve.isPending ||
    refreshDatabases.isPending;
  const stage = setup?.stage;
  const setupError =
    saveSetup.error ||
    importTasks.error ||
    loadAvailability.error ||
    solve.error ||
    (usingNotion ? refreshDatabases.error || notionDatabases.error : null);
  const needsTaskSource = usingNotion ? !databaseId : tasks.length === 0;
  const needsCalendar = !calendarId;

  const chooseManualTasks = () => {
    setTaskSource("manual");
    setDatabaseId("");
    refreshDatabases.reset();
  };

  const chooseNotionTasks = () => {
    setTaskSource("notion");
    if (
      hasNotion &&
      !notionDatabases.data?.length &&
      !notionDatabases.isFetching
    ) {
      refreshDatabases.mutate();
    }
  };

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice
        {...planSetupNextStep(
          stage,
          busy,
          usingNotion,
          databaseId,
          tasks.length,
          hasGoogle,
          calendarId,
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
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <label className="field">
              Calendar Relay schedules into
              {hasGoogle ? (
                <select
                  value={calendarId}
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
              ) : (
                <span className="text-sm text-muted">
                  <Link className="text-link" href="/connections">
                    Connect Google Calendar
                  </Link>{" "}
                  to choose a calendar. Relay needs one to schedule study
                  blocks.
                </span>
              )}
            </label>
            <div className="field">
              <span className="field-label">Task source</span>
              <div className="task-source-options" role="radiogroup">
                <button
                  type="button"
                  className={`task-source-option ${!usingNotion ? "selected" : ""}`}
                  aria-pressed={!usingNotion}
                  onClick={chooseManualTasks}
                >
                  <Keyboard aria-hidden="true" />
                  <span>
                    <strong>Enter tasks manually</strong>
                    <small>Add and reorder tasks in Relay.</small>
                  </span>
                </button>
                <button
                  type="button"
                  className={`task-source-option ${usingNotion ? "selected" : ""}`}
                  aria-pressed={usingNotion}
                  disabled={!hasNotion}
                  onClick={chooseNotionTasks}
                >
                  <Database aria-hidden="true" />
                  <span>
                    <strong>Import from Notion</strong>
                    <small>Choose a task database to pull from.</small>
                  </span>
                </button>
              </div>
              {!hasNotion && (
                <span className="text-sm text-muted">
                  <Link className="text-link" href="/connections">
                    Connect Notion
                  </Link>{" "}
                  to import tasks from a database.
                </span>
              )}
              {usingNotion && hasNotion && (
                <div className="task-source-picker">
                  <div className="destination-picker-heading">
                    <span className="field-label">Choose Notion database</span>
                    <button
                      className="icon-button"
                      disabled={busy}
                      onClick={() => refreshDatabases.mutate()}
                      aria-label="Refresh Notion databases"
                      title="Refresh Notion databases"
                      type="button"
                    >
                      <RotateCcw aria-hidden="true" />
                    </button>
                  </div>
                  <select
                    value={databaseId}
                    onChange={(event) => setDatabaseId(event.target.value)}
                  >
                    <option value="">Select a Notion database</option>
                    {(notionDatabases.data || []).map((database) => (
                      <option key={database.id} value={database.id}>
                        {database.title}
                      </option>
                    ))}
                  </select>
                  <p className="text-sm text-muted">
                    {notionDatabases.isFetching || refreshDatabases.isPending
                      ? "Loading Notion databases..."
                      : (notionDatabases.data || []).length === 0
                        ? "No databases found. Refresh after sharing a database with the Relay Notion integration."
                        : "Select the database that contains the tasks Relay should schedule."}
                  </p>
                </div>
              )}
            </div>
          </div>
          {usingNotion && databaseId && (
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
                  Category property (optional)
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
                  Priority property (optional)
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
          {!usingNotion && (
            <div className="mt-6 border-t border-line pt-5">
              <TaskTable tasks={tasks} onChange={setTasks} editable />
            </div>
          )}
          <button
            className="button mt-6"
            disabled={busy || needsTaskSource || needsCalendar}
            onClick={() => saveSetup.mutate({})}
          >
            {saveSetup.isPending
              ? "Saving..."
              : "Next: import or confirm tasks"}
          </button>
        </div>
      ) : null}

      {!editingSetup && stage === "setup" && (
        <div className="panel">
          <div className="section-heading">
            <h2 className="section-title">Import tasks</h2>
            <button
              type="button"
              className="text-link text-sm"
              onClick={() => setEditingSetup(true)}
            >
              Edit planning window &amp; sources
            </button>
          </div>
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
            Next: import tasks
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
              Next: load calendar availability
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
            Next: generate study plan
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
  const missingCalendar = !setup?.calendar_id;
  const canRequestApproval =
    data.run.status === "PLAN_READY" &&
    !!result &&
    result.status !== "INFEASIBLE" &&
    result.sessions.length > 0 &&
    !missingCalendar;
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
          {!canRequestApproval && missingCalendar && (
            <p className="mt-3 text-sm text-muted">
              This plan has no calendar selected, so Relay cannot request
              approval for it.{" "}
              <Link className="text-link" href="/connections">
                Connect Google Calendar
              </Link>
              , then start a new study plan to choose it during setup.
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
