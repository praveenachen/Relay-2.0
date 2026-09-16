"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  ExternalLink,
  ListTodo,
  MoreHorizontal,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useConnections, usePreferences, useProject } from "@/hooks/queries";
import { Empty, ErrorMessage, Loading, Spinner } from "@/components/ui";
import {
  projectTaskFromServer,
  taskDeadlineValue,
  type ProjectTask,
} from "@/lib/project-tasks";
import { SourceCaptureModal } from "@/components/source-capture-modal";
import { projects, type Project } from "@/features/projects/api";
import { connections } from "@/features/connections/api";
import type { SourceType } from "@/features/sources/api";
import { sources } from "@/features/sources/api";
import {
  plan,
  projectActions,
  type GitHubIssuePreview,
  type NotionProjectPreview,
  type PlanDetail,
  type StudySession,
} from "@/features/plan/api";
import { useProjectSources, useServerTasks } from "@/hooks/queries";
import {
  ScheduleBlockModal,
  sessionKey,
  validateSessionPlacement,
  WeeklyCalendar,
} from "@/components/weekly-calendar";

const tabs = ["overview", "tasks", "plan", "sources"] as const;
type Tab = (typeof tabs)[number];
const statusLabels = {
  TODO: "Todo",
  IN_PROGRESS: "In progress",
  DONE: "Done",
} as const;
const addOptions = {
  SCHOOL: [
    ["Assignment / brief", "ASSIGNMENT_BRIEF"],
    ["Course outline", "COURSE_OUTLINE"],
    ["Study goal", "STUDY_GOAL"],
  ],
  WORK: [
    ["Meeting notes / transcript", "MEETING_TRANSCRIPT"],
    ["Document / brief", "DOCUMENT_BRIEF"],
  ],
  PERSONAL: [
    ["Goal / project idea", "PERSONAL_GOAL"],
    ["Notes / checklist", "NOTES_CHECKLIST"],
  ],
} as const;

function TaskModal({
  projectId,
  close,
  save,
}: {
  projectId: string;
  close: () => void;
  save: (task: ProjectTask) => void;
}) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [estimate, setEstimate] = useState("");
  const [priority, setPriority] = useState<ProjectTask["priority"]>("MEDIUM");
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        className="project-modal compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-title"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Quick add</p>
            <h2 id="task-title">New task</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save({
              id: crypto.randomUUID(),
              projectId,
              title: title.trim(),
              status: "TODO",
              priority,
              dueDate: dueDate || null,
              estimate: estimate ? Number(estimate) : null,
            });
          }}
        >
          <label className="field">
            Task title
            <input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="What needs doing?"
            />
          </label>
          <div className="form-split">
            <label className="field">
              Due date <span className="optional">Optional</span>
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </label>
            <label className="field">
              Estimate <span className="optional">Minutes</span>
              <input
                type="number"
                min={5}
                step={5}
                value={estimate}
                onChange={(event) => setEstimate(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            Priority
            <select
              value={priority}
              onChange={(event) =>
                setPriority(event.target.value as ProjectTask["priority"])
              }
            >
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
            </select>
          </label>
          <div className="modal-actions">
            <button type="button" className="button secondary" onClick={close}>
              Cancel
            </button>
            <button className="button" disabled={!title.trim()}>
              Add task
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function TaskEditModal({
  task,
  close,
  save,
}: {
  task: ProjectTask;
  close: () => void;
  save: (task: ProjectTask) => Promise<void>;
}) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || "");
  const [dueDate, setDueDate] = useState(task.dueDate || "");
  const [estimate, setEstimate] = useState(
    task.estimate ? String(task.estimate) : "",
  );
  const [priority, setPriority] = useState(task.priority);
  const [status, setStatus] = useState(task.status);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        className="project-modal compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-task-title"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Task details</p>
            <h2 id="edit-task-title">Edit task</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError(null);
            try {
              await save({
                ...task,
                title: title.trim(),
                description: description.trim() || null,
                dueDate: dueDate || null,
                estimate: estimate ? Number(estimate) : null,
                priority,
                status,
              });
            } catch (saveError) {
              setError(saveError);
            } finally {
              setPending(false);
            }
          }}
        >
          <label className="field">
            Task title
            <input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label className="field">
            Description <span className="optional">Optional</span>
            <textarea
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <div className="form-split">
            <label className="field">
              Due date <span className="optional">Optional</span>
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </label>
            <label className="field">
              Estimate <span className="optional">Minutes</span>
              <input
                type="number"
                min={5}
                max={1440}
                step={5}
                value={estimate}
                onChange={(event) => setEstimate(event.target.value)}
              />
            </label>
          </div>
          <div className="form-split">
            <label className="field">
              Priority
              <select
                value={priority}
                onChange={(event) =>
                  setPriority(event.target.value as ProjectTask["priority"])
                }
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
              </select>
            </label>
            <label className="field">
              Status
              <select
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as ProjectTask["status"])
                }
              >
                <option value="TODO">Todo</option>
                <option value="IN_PROGRESS">In progress</option>
                <option value="DONE">Done</option>
              </select>
            </label>
          </div>
          <ErrorMessage error={error} title="Couldn’t update this task" />
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={close}
              disabled={pending}
            >
              Cancel
            </button>
            <button className="button" disabled={!title.trim() || pending}>
              {pending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function DeleteProjectModal({
  name,
  close,
  confirm,
  pending,
  error,
}: {
  name: string;
  close: () => void;
  confirm: () => void;
  pending: boolean;
  error: unknown;
}) {
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        className="project-modal compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-project-title"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">This can’t be undone</p>
            <h2 id="delete-project-title">Delete “{name}”?</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        <div className="modal-stack">
          <p className="modal-body-text">
            This permanently removes its tasks, sources, and pending proposals.
          </p>
          <ErrorMessage error={error} title="Couldn’t delete this project" />
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={close}
              disabled={pending}
            >
              Cancel
            </button>
            <button
              type="button"
              className="button reject-button"
              onClick={confirm}
              disabled={pending}
            >
              {pending ? "Deleting…" : "Delete project"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const project = useProject(id);
  const cache = useQueryClient();
  const requestedTab = search.get("tab")?.toLowerCase();
  const [tab, setTab] = useState<Tab>(
    tabs.includes(requestedTab as Tab) ? (requestedTab as Tab) : "overview",
  );
  const serverTasks = useServerTasks(id);
  const remoteTasks: ProjectTask[] = (serverTasks.data || []).map(
    projectTaskFromServer,
  );
  const tasks = remoteTasks;
  const [addingTask, setAddingTask] = useState(false);
  const [addingSource, setAddingSource] = useState<SourceType | null>(null);
  const [editingTask, setEditingTask] = useState<ProjectTask | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const chooseTab = (next: Tab) => {
    setTab(next);
    router.replace(`/projects/${id}?tab=${next}`, { scroll: false });
  };
  const deleteProject = useMutation({
    mutationFn: () => projects.delete(id),
    onSuccess: () => {
      cache.setQueryData<Project[]>(["projects"], (current = []) =>
        current.filter((p) => p.id !== id),
      );
      cache.invalidateQueries({ queryKey: ["tasks"] });
      cache.invalidateQueries({ queryKey: ["schedule"] });
      router.replace(
        `/spaces/${(project.data?.space || "personal").toLowerCase()}`,
      );
    },
  });
  const createTask = useMutation({
    mutationFn: (task: ProjectTask) =>
      sources.createTask(id, {
        title: task.title,
        due_date: taskDeadlineValue(task),
        estimate_minutes: task.estimate,
        priority: task.priority,
        status: task.status,
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["projects", id, "tasks"] });
      cache.invalidateQueries({ queryKey: ["tasks"] });
      setAddingTask(false);
      chooseTab("tasks");
    },
  });
  const updateTask = useMutation({
    mutationFn: (task: ProjectTask) =>
      sources.updateTask(id, task.id, {
        title: task.title,
        description: task.description,
        due_date: taskDeadlineValue(task),
        estimate_minutes: task.estimate,
        priority: task.priority,
        status: task.status,
      }),
    onSuccess: () =>
      Promise.all([
        cache.invalidateQueries({ queryKey: ["projects", id, "tasks"] }),
        cache.invalidateQueries({ queryKey: ["tasks"] }),
      ]),
  });
  if (project.isPending) return <Loading label="Loading project" />;
  if (project.error || !project.data)
    return (
      <ErrorMessage error={project.error || new Error("Project not found.")} />
    );
  const item = project.data;
  const done = tasks.filter((task) => task.status === "DONE").length;
  const progress = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
  return (
    <>
      <Link
        className="project-back"
        href={`/spaces/${item.space.toLowerCase()}`}
      >
        ← {item.space.toLowerCase()}
      </Link>
      <header className="project-header">
        <div>
          <div className={`space-chip ${item.space.toLowerCase()}`}>
            {item.space.toLowerCase()}
          </div>
          <h1>{item.name}</h1>
          <div className="project-header-meta">
            {item.deadline && (
              <span>
                <CalendarDays /> Due{" "}
                {new Date(item.deadline).toLocaleDateString(undefined, {
                  month: "long",
                  day: "numeric",
                })}
              </span>
            )}
            <span>
              <CheckCircle2 />{" "}
              {tasks.length ? `${progress}% complete` : "No tasks yet"}
            </span>
          </div>
        </div>
        <div className="project-header-actions">
          <details className="add-menu">
            <summary className="button">
              <Plus /> Add
            </summary>
            <div className="add-popover">
              <button onClick={() => setAddingTask(true)}>
                <ListTodo />
                Task
              </button>
              {addOptions[item.space].map(([label, sourceType]) => (
                <button key={label} onClick={() => setAddingSource(sourceType)}>
                  <FileText />
                  {label}
                </button>
              ))}
            </div>
          </details>
          <button
            className="icon-button"
            onClick={() => setConfirmingDelete(true)}
            aria-label="Delete project"
            title="Delete project"
          >
            <Trash2 />
          </button>
        </div>
      </header>
      <nav className="project-tabs" aria-label="Project sections">
        {tabs.map((value) => (
          <button
            key={value}
            className={tab === value ? "active" : ""}
            aria-current={tab === value ? "page" : undefined}
            onClick={() => chooseTab(value)}
          >
            {value[0].toUpperCase() + value.slice(1)}
          </button>
        ))}
      </nav>
      {tab === "overview" && (
        <Overview
          project={item}
          description={item.description}
          tasks={tasks}
          deadline={item.deadline}
          onAdd={() => setAddingTask(true)}
          onTab={chooseTab}
        />
      )}
      {tab === "tasks" && (
        <TaskView
          tasks={tasks}
          updateServer={(task) =>
            updateTask.mutateAsync(task).then(() => undefined)
          }
          project={item}
          onAdd={() => setAddingTask(true)}
          onEdit={setEditingTask}
        />
      )}
      {tab === "plan" && (
        <PlanView project={item} tasks={tasks} onEdit={setEditingTask} />
      )}
      {tab === "sources" && <SourcesView projectId={id} project={item} />}
      {addingTask && (
        <TaskModal
          projectId={id}
          close={() => setAddingTask(false)}
          save={(task) => {
            createTask.mutate(task);
          }}
        />
      )}
      {addingSource && (
        <SourceCaptureModal
          projectId={id}
          sourceType={addingSource}
          close={() => setAddingSource(null)}
        />
      )}
      {confirmingDelete && (
        <DeleteProjectModal
          name={item.name}
          close={() => setConfirmingDelete(false)}
          confirm={() => deleteProject.mutate()}
          pending={deleteProject.isPending}
          error={deleteProject.error}
        />
      )}
      {editingTask && (
        <TaskEditModal
          task={editingTask}
          close={() => setEditingTask(null)}
          save={async (edited) => {
            await updateTask.mutateAsync(edited).then(() => undefined);
            setEditingTask(null);
          }}
        />
      )}
    </>
  );
}

function Overview({
  project,
  description,
  tasks,
  deadline,
  onAdd,
  onTab,
}: {
  project: Project;
  description: string | null;
  tasks: ProjectTask[];
  deadline: string | null;
  onAdd: () => void;
  onTab: (tab: Tab) => void;
}) {
  const open = tasks.filter((task) => task.status !== "DONE");
  return (
    <div className="overview-grid">
      <section className="project-surface overview-main">
        <p className="eyebrow">Project goal</p>
        <h2 className="project-goal" title={description || undefined}>
          {description || "Give this project a clear next step."}
        </h2>
        <p>
          {description
            ? "Keep momentum by choosing the next useful task."
            : "Add tasks now; richer project editing will arrive in a later phase."}
        </p>
        <button className="button secondary" onClick={onAdd}>
          <Plus /> Add a task
        </button>
      </section>
      <aside className="project-surface snapshot">
        <h2>At a glance</h2>
        <dl>
          <div>
            <dt>Open tasks</dt>
            <dd>{open.length}</dd>
          </div>
          <div>
            <dt>Completed</dt>
            <dd>
              {tasks.length
                ? `${Math.round(((tasks.length - open.length) / tasks.length) * 100)}%`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Deadline</dt>
            <dd>
              {deadline
                ? new Date(deadline).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })
                : "Not set"}
            </dd>
          </div>
        </dl>
      </aside>
      <section className="project-surface next-tasks">
        <div className="surface-heading">
          <div>
            <p className="eyebrow">Next up</p>
            <h2>Open tasks</h2>
          </div>
          <button className="text-link" onClick={() => onTab("tasks")}>
            View all
          </button>
        </div>
        {open.length ? (
          <ul>
            {open.slice(0, 3).map((task) => (
              <li key={task.id}>
                <Circle />
                <span>{task.title}</span>
                {task.dueDate && (
                  <time>
                    {new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(
                      undefined,
                      { month: "short", day: "numeric" },
                    )}
                  </time>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="surface-empty">
            Nothing queued yet. Add the first small step.
          </p>
        )}
      </section>
      <NotionPublishCard project={project} />
    </div>
  );
}

function NotionPublishCard({ project }: { project: Project }) {
  const cache = useQueryClient();
  const [choosingDestination, setChoosingDestination] = useState(false);
  const [destinationChoice, setDestinationChoice] = useState("");
  const status = useQuery({
    queryKey: ["projects", project.id, "notion"],
    queryFn: () => projectActions.notionStatus(project.id),
  });
  const destinations = useQuery({
    queryKey: ["connections", "notion-destinations"],
    queryFn: async () => {
      const cached = await connections.notionDestinations();
      return cached.length ? cached : connections.refreshNotionDestinations();
    },
    enabled: choosingDestination,
  });
  const refreshDestinations = useMutation({
    mutationFn: connections.refreshNotionDestinations,
    onSuccess: (items) => {
      cache.setQueryData(["connections", "notion-destinations"], items);
      if (!items.some((item) => item.id === destinationChoice)) {
        setDestinationChoice("");
      }
    },
  });
  const selectDestination = useMutation({
    mutationFn: () => connections.selectNotionDestination(destinationChoice),
    onSuccess: async () => {
      setChoosingDestination(false);
      setDestinationChoice("");
      setPreview(null);
      await cache.invalidateQueries({
        queryKey: ["projects", project.id, "notion"],
      });
    },
  });
  const [preview, setPreview] = useState<NotionProjectPreview | null>(null);
  const prepare = useMutation({
    mutationFn: () => projectActions.previewNotionProject(project.id),
    onSuccess: setPreview,
  });
  const publish = useMutation({
    mutationFn: async () => {
      const run = await projectActions.confirmNotionProject(
        project.id,
        preview!.run_id,
        preview!.approval_id,
      );
      if (run.status !== "COMPLETED") {
        throw new Error(
          "Notion couldn’t update this project. Your Relay project is unchanged; try again.",
        );
      }
      return run;
    },
    onSuccess: async () => {
      setPreview(null);
      await cache.invalidateQueries({
        queryKey: ["projects", project.id, "notion"],
      });
    },
    onError: () => setPreview(null),
  });
  const info = status.data;
  return (
    <section className="project-surface notion-publish-card">
      <div className="surface-heading">
        <div>
          <p className="eyebrow">Notion</p>
          <h2>
            {info?.page_id ? "Project published" : "Publish this project"}
          </h2>
        </div>
        {info?.page_url && (
          <a
            className="text-link"
            href={info.page_url}
            target="_blank"
            rel="noreferrer"
          >
            Open in Notion <ExternalLink />
          </a>
        )}
      </div>
      {status.isPending ? (
        <p className="surface-empty">Checking your Notion connection…</p>
      ) : !info?.connected ? (
        <div className="notion-connect-state">
          <p>Connect Notion to publish a clean project page.</p>
          <Link className="button secondary" href="/connections">
            Connect Notion
          </Link>
        </div>
      ) : !info.destination_configured ? (
        <div className="notion-connect-state">
          <p>Select the Notion page where Relay should publish projects.</p>
          <button
            className="button secondary"
            onClick={() => setChoosingDestination(true)}
          >
            Choose destination
          </button>
        </div>
      ) : (
        <>
          <p className="notion-publish-copy">
            {info.page_id
              ? "Refresh the same Notion page with your latest progress, tasks, plan, and sources."
              : `Create a focused project page inside ${info.destination_title || "your selected destination"}.`}
          </p>
          <button
            className="button"
            onClick={() => prepare.mutate()}
            disabled={prepare.isPending || publish.isPending}
          >
            {prepare.isPending && <Spinner label="Preparing Notion project" />}
            {prepare.isPending
              ? "Preparing…"
              : info.page_id
                ? "Update Notion"
                : "Publish to Notion"}
          </button>
          <button
            className="text-link notion-change-destination"
            onClick={() => setChoosingDestination((current) => !current)}
          >
            Change destination
          </button>
        </>
      )}
      {choosingDestination && info?.connected && (
        <div className="notion-destination-picker">
          <div>
            <strong>Choose a Notion page</strong>
            <p>Relay will create the project page inside this destination.</p>
          </div>
          {destinations.isPending ? (
            <p className="surface-empty">Loading pages from Notion…</p>
          ) : (
            <div className="notion-destination-controls">
              <select
                aria-label="Notion project destination"
                value={destinationChoice}
                onChange={(event) => setDestinationChoice(event.target.value)}
              >
                <option value="">Select a page</option>
                {(refreshDestinations.data || destinations.data || []).map(
                  (destination) => (
                    <option key={destination.id} value={destination.id}>
                      {destination.title}
                    </option>
                  ),
                )}
              </select>
              <button
                className="button"
                disabled={!destinationChoice || selectDestination.isPending}
                onClick={() => selectDestination.mutate()}
              >
                {selectDestination.isPending ? "Saving…" : "Use this page"}
              </button>
              <button
                className="text-link"
                disabled={refreshDestinations.isPending}
                onClick={() => refreshDestinations.mutate()}
              >
                {refreshDestinations.isPending
                  ? "Refreshing…"
                  : "Refresh pages"}
              </button>
            </div>
          )}
          {!destinations.isPending &&
            !(refreshDestinations.data || destinations.data || []).length && (
              <p className="notion-destination-empty">
                No pages are available. In Notion, share a page with the Relay
                integration, then refresh.
              </p>
            )}
          <ErrorMessage
            error={
              destinations.error ||
              refreshDestinations.error ||
              selectDestination.error
            }
            title="Couldn’t load Notion pages"
          />
        </div>
      )}
      <ErrorMessage
        error={status.error || prepare.error || publish.error}
        title="Couldn’t publish this project"
      />
      {preview && (
        <div
          className="notion-preview"
          role="dialog"
          aria-label="Confirm Notion publish"
        >
          <div>
            <p className="eyebrow">Preview</p>
            <h3>{preview.title}</h3>
            <p>
              {preview.progress}% complete · {preview.task_count} tasks ·{" "}
              {preview.source_count} sources
            </p>
            {preview.deadline && (
              <p>Deadline {new Date(preview.deadline).toLocaleDateString()}</p>
            )}
          </div>
          <div className="notion-preview-actions">
            <button
              className="button secondary"
              onClick={() => setPreview(null)}
            >
              Cancel
            </button>
            <button
              className="button"
              onClick={() => publish.mutate()}
              disabled={publish.isPending}
            >
              {publish.isPending && (
                <Spinner label="Publishing Notion project" />
              )}
              {publish.isPending
                ? "Publishing…"
                : preview.is_update
                  ? "Confirm update"
                  : "Confirm publish"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function TaskView({
  tasks,
  updateServer,
  project,
  onAdd,
  onEdit,
}: {
  tasks: ProjectTask[];
  updateServer: (task: ProjectTask) => Promise<void>;
  project: Project;
  onAdd: () => void;
  onEdit: (task: ProjectTask) => void;
}) {
  const [issueTask, setIssueTask] = useState<ProjectTask | null>(null);
  const change = (id: string, status: ProjectTask["status"]) => {
    const current = tasks.find((task) => task.id === id);
    if (current) void updateServer({ ...current, status });
  };
  return (
    <section className="project-surface task-surface">
      <div className="surface-heading">
        <div>
          <p className="eyebrow">Simple and focused</p>
          <h2>Tasks</h2>
        </div>
        <button className="button secondary" onClick={onAdd}>
          <Plus /> Add task
        </button>
      </div>
      {tasks.length ? (
        <div className="task-groups">
          {(["TODO", "IN_PROGRESS", "DONE"] as const).map((status) => (
            <section key={status} className="task-group">
              <div className="task-group-title">
                <h3>{statusLabels[status]}</h3>
                <span>
                  {tasks.filter((task) => task.status === status).length}
                </span>
              </div>
              {tasks
                .filter((task) => task.status === status)
                .map((task) => (
                  <article className="task-row" key={task.id}>
                    <button
                      aria-label={`Move ${task.title} forward`}
                      onClick={() =>
                        change(
                          task.id,
                          status === "TODO"
                            ? "IN_PROGRESS"
                            : status === "IN_PROGRESS"
                              ? "DONE"
                              : "TODO",
                        )
                      }
                    >
                      {status === "DONE" ? <CheckCircle2 /> : <Circle />}
                    </button>
                    <div>
                      <strong>{task.title}</strong>
                      <p>
                        <span
                          className={`priority ${task.priority.toLowerCase()}`}
                        >
                          {task.priority.toLowerCase()}
                        </span>
                        {task.estimate && (
                          <span>
                            <Clock3 /> {task.estimate}m
                          </span>
                        )}
                        {task.dueDate && (
                          <span>
                            <CalendarDays />{" "}
                            {new Date(
                              `${task.dueDate}T12:00:00`,
                            ).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                            })}
                          </span>
                        )}
                        {task.sourceTitle && (
                          <span className="task-source">
                            From {task.sourceTitle}
                            {task.sourceReference
                              ? ` · ${task.sourceReference}`
                              : ""}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="task-row-actions">
                      {task.externalReferences?.map((reference) => (
                        <a
                          key={reference.url}
                          href={reference.url}
                          target="_blank"
                          rel="noreferrer"
                          className="button secondary"
                        >
                          Open GitHub issue
                        </a>
                      ))}
                      {task.server &&
                        !task.externalReferences?.some(
                          (reference) => reference.provider === "GITHUB",
                        ) && (
                          <button
                            className="icon-button icon-text-button"
                            aria-label={`Add ${task.title} to GitHub repo`}
                            title="Add to GitHub repo"
                            onClick={() => setIssueTask(task)}
                          >
                            Add to GitHub repo
                          </button>
                        )}
                      <button
                        className="icon-button"
                        aria-label={`Edit ${task.title}`}
                        title="Edit task"
                        onClick={() => onEdit(task)}
                      >
                        <MoreHorizontal />
                      </button>
                    </div>
                  </article>
                ))}
            </section>
          ))}
        </div>
      ) : (
        <Empty title="No tasks yet.">
          Add a first task to turn this project into a plan.
        </Empty>
      )}
      {issueTask && (
        <GitHubIssueModal
          project={project}
          task={issueTask}
          close={() => setIssueTask(null)}
        />
      )}
    </section>
  );
}

function GitHubIssueModal({
  project,
  task,
  close,
}: {
  project: Project;
  task: ProjectTask;
  close: () => void;
}) {
  const cache = useQueryClient();
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || "");
  const [repository, setRepository] = useState("");
  const [preview, setPreview] = useState<GitHubIssuePreview | null>(null);
  const [connectedRepo, setConnectedRepo] = useState<{
    owner: string;
    name: string;
  } | null>(null);
  const connectionQuery = useConnections();
  const createPreview = useMutation({
    mutationFn: () =>
      projectActions.previewGitHubIssue(project.id, task.id, {
        title,
        description,
      }),
    onSuccess: setPreview,
  });
  const confirm = useMutation({
    mutationFn: async () => {
      const run = await projectActions.confirmGitHubIssue(
        project.id,
        task.id,
        preview!.run_id,
        preview!.approval_id,
      );
      if (run.status !== "COMPLETED") {
        throw new Error(
          run.error_message ||
            "The GitHub issue was not created. Check Activity before retrying.",
        );
      }
      return run;
    },
    onSuccess: async () => {
      await cache.invalidateQueries({
        queryKey: ["projects", project.id, "tasks"],
      });
      close();
    },
  });
  const repoOwner = connectedRepo?.owner || project.github_repository_owner;
  const repoName = connectedRepo?.name || project.github_repository_name;
  const hasRepository = Boolean(repoOwner && repoName);
  const hasGitHubConnection = (connectionQuery.data || []).some(
    (item) => item.provider === "GITHUB" && item.status === "CONNECTED",
  );
  const repositories = useQuery({
    queryKey: ["connections", "github-repositories"],
    queryFn: connections.githubRepositories,
    enabled: !hasRepository && hasGitHubConnection,
  });
  const refreshRepositories = useMutation({
    mutationFn: connections.githubRepositories,
    onSuccess: (items) => {
      cache.setQueryData(["connections", "github-repositories"], items);
    },
  });
  const selectRepository = useMutation({
    mutationFn: () => {
      const selected = repositories.data?.find(
        (item) => `${item.owner}/${item.name}` === repository,
      );
      if (!selected) throw new Error("Select a repository.");
      return projects.update(project.id, {
        name: project.name,
        space: project.space,
        description: project.description,
        deadline: project.deadline,
        course: project.course,
        notion_database_id: project.notion_database_id,
        notion_property_mapping: project.notion_property_mapping,
        github_repository_owner: selected.owner,
        github_repository_name: selected.name,
      });
    },
    onSuccess: (updated) => {
      cache.setQueryData(["projects", project.id], updated);
      // Resume straight into issue creation instead of requiring the user
      // to close and reopen this modal.
      setConnectedRepo({
        owner: updated.github_repository_owner!,
        name: updated.github_repository_name!,
      });
    },
  });
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="project-modal compact"
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">GitHub</p>
            <h2>Create GitHub issue</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        {!hasRepository ? (
          <div className="modal-stack">
            <p>
              Select a repository for this project before creating an issue.
            </p>
            {repositories.isPending ? (
              <p className="generation-status surface-empty" role="status">
                <Spinner label="Loading repositories" />
                Loading repositories…
              </p>
            ) : repositories.data?.length ? (
              <>
                <label className="field">
                  Repository
                  <select
                    value={repository}
                    onChange={(event) => setRepository(event.target.value)}
                  >
                    <option value="">Select a repository</option>
                    {repositories.data.map((item) => (
                      <option
                        key={`${item.owner}/${item.name}`}
                        value={`${item.owner}/${item.name}`}
                      >
                        {item.full_name}
                      </option>
                    ))}
                  </select>
                </label>
                <ErrorMessage
                  error={selectRepository.error}
                  title="Repository couldn’t be selected."
                />
                <button
                  className="button"
                  disabled={!repository || selectRepository.isPending}
                  onClick={() => selectRepository.mutate()}
                >
                  {selectRepository.isPending && (
                    <Spinner label="Selecting repository" />
                  )}
                  Select repository
                </button>
                <button
                  className="button secondary"
                  disabled={refreshRepositories.isPending}
                  onClick={() => refreshRepositories.mutate()}
                >
                  {refreshRepositories.isPending && (
                    <Spinner label="Refreshing repositories" />
                  )}
                  Refresh repositories
                </button>
              </>
            ) : (
              <div className="modal-stack">
                {hasGitHubConnection ? (
                  <button
                    className="button secondary"
                    disabled={refreshRepositories.isPending}
                    onClick={() => refreshRepositories.mutate()}
                  >
                    {refreshRepositories.isPending && (
                      <Spinner label="Refreshing repositories" />
                    )}
                    Refresh repositories
                  </button>
                ) : connectionQuery.isPending ? (
                  <p className="surface-empty">Checking GitHub connection…</p>
                ) : (
                  <Link className="button secondary" href="/connections">
                    Connect GitHub
                  </Link>
                )}
                <ErrorMessage
                  error={repositories.error || refreshRepositories.error}
                  retry={() => refreshRepositories.mutate()}
                  title="Repositories couldn’t be loaded."
                />
              </div>
            )}
          </div>
        ) : (
          <div className="modal-stack">
            <p className="modal-body-text">
              Repository: {repoOwner}/{repoName}
            </p>
            <label className="field">
              Title
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="field">
              Description
              <textarea
                rows={5}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <ErrorMessage
              error={createPreview.error || confirm.error}
              title="GitHub issue couldn’t be created."
            />
            {preview && (
              <div className="approval-preview">
                <strong>{preview.title}</strong>
                <p>{preview.description || "No description"}</p>
                <small>{preview.repository}</small>
              </div>
            )}
            <div className="modal-actions">
              <button className="button secondary" onClick={close}>
                Cancel
              </button>
              {!preview ? (
                <button
                  className="button"
                  disabled={!title.trim() || createPreview.isPending}
                  onClick={() => createPreview.mutate()}
                >
                  {createPreview.isPending && (
                    <Spinner label="Generating GitHub issue preview" />
                  )}
                  {createPreview.isPending ? "Preparing…" : "Preview issue"}
                </button>
              ) : (
                <button
                  className="button"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate()}
                >
                  {confirm.isPending && (
                    <Spinner label="Creating GitHub issue" />
                  )}
                  {confirm.isPending ? "Adding…" : "Add to GitHub repo"}
                </button>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function PlanView({
  project,
  tasks,
  onEdit,
}: {
  project: Project;
  tasks: ProjectTask[];
  onEdit: (task: ProjectTask) => void;
}) {
  const open = tasks.filter((task) => task.status !== "DONE");
  const schedulable = open.filter(
    (task) => task.server && task.dueDate && task.estimate,
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<PlanDetail | null>(null);
  const [editingSession, setEditingSession] = useState<StudySession | null>(
    null,
  );
  const [placementError, setPlacementError] = useState<string | null>(null);
  const [calendarChoice, setCalendarChoice] = useState("");
  const cache = useQueryClient();
  const preferencesQuery = usePreferences();
  const connectionQuery = useConnections();
  const googleConnection = (connectionQuery.data || []).find(
    (item) => item.provider === "GOOGLE" && item.status === "CONNECTED",
  );
  const configuredCalendarId =
    googleConnection?.provider_metadata.default_calendar_id;
  const calendarId =
    typeof configuredCalendarId === "string" ? configuredCalendarId : "";
  const configuredCalendarSummary =
    googleConnection?.provider_metadata.default_calendar_summary;
  const calendarSummary =
    typeof configuredCalendarSummary === "string"
      ? configuredCalendarSummary
      : calendarId;
  const googleCalendars = useQuery({
    queryKey: ["connections", "google-calendars"],
    queryFn: connections.googleCalendars,
    enabled: Boolean(googleConnection && !calendarId),
  });
  const refreshCalendars = useMutation({
    mutationFn: connections.refreshGoogleCalendars,
    onSuccess: () =>
      cache.invalidateQueries({
        queryKey: ["connections", "google-calendars"],
      }),
  });
  const generate = useMutation({
    mutationFn: () => {
      const start = new Date();
      start.setHours(0, 0, 0, 0);
      const end = new Date(start);
      end.setDate(end.getDate() + 7);
      return plan.createProjectPlan(project.id, {
        task_ids: selected,
        start: start.toISOString(),
        end: end.toISOString(),
        calendar_id: calendarId || null,
      });
    },
    onSuccess: setResult,
  });
  const adjustSessions = useMutation({
    mutationFn: (sessions: StudySession[]) =>
      plan.adjustSessions(result!.run.id, sessions),
    onSuccess: (next) => {
      setResult(next);
      setEditingSession(null);
    },
  });
  const addToCalendar = useMutation({
    mutationFn: async () => {
      const run = await plan.approveAndExecute(result!.run.id);
      if (run.status !== "COMPLETED") {
        throw new Error(
          run.error_message ||
            "Some time blocks were not added to Google Calendar. Check Activity before retrying.",
        );
      }
      return run;
    },
    onSettled: () => cache.invalidateQueries({ queryKey: ["schedule"] }),
  });
  const selectCalendar = useMutation({
    mutationFn: () => connections.selectGoogleCalendar(calendarChoice),
    onSuccess: async () => {
      addToCalendar.reset();
      generate.reset();
      setResult(null);
      await cache.invalidateQueries({ queryKey: ["connections"] });
    },
  });
  const taskTitle = (id: string) =>
    tasks.find((task) => task.id === id)?.title || "Project task";
  const updateSession = (key: string, start: Date, duration?: number) => {
    if (!result?.result) return;
    const current = result.result.sessions.find(
      (session) => sessionKey(session) === key,
    );
    if (!current) return;
    const minutes =
      duration ??
      Math.round(
        (new Date(current.end).getTime() - new Date(current.start).getTime()) /
          60000,
      );
    const setupTask = result.setup?.tasks.find(
      (task) => task.id === current.task_id,
    );
    const userPreferences = preferencesQuery.data;
    if (userPreferences && result.setup) {
      const message = validateSessionPlacement({
        key,
        taskId: current.task_id,
        start,
        duration: minutes,
        sessions: result.result.sessions,
        busyIntervals: result.setup.busy_intervals,
        windowStart: result.setup.window.start,
        windowEnd: result.setup.window.end,
        preferences: {
          earliest: userPreferences.earliest_study_time,
          latest: userPreferences.latest_study_time,
          maximumSessionMinutes: userPreferences.maximum_session_minutes,
          minimumBreakMinutes: userPreferences.minimum_break_minutes,
        },
        deadline: setupTask?.deadline,
        estimatedMinutes: setupTask?.estimated_minutes,
      });
      if (message) {
        setPlacementError(message);
        return;
      }
    }
    setPlacementError(null);
    const sessions = result.result.sessions.map((session) => {
      if (sessionKey(session) !== key) return session;
      return {
        ...session,
        start: start.toISOString(),
        end: new Date(start.getTime() + minutes * 60000).toISOString(),
        locked: true,
      };
    });
    adjustSessions.mutate(sessions);
  };
  return (
    <section className="plan-panel">
      <div className="plan-panel-intro">
        <p className="eyebrow">Plan</p>
        <h2>Plan your project</h2>
        <p>
          Turn your project tasks into focused time blocks around your existing
          schedule.
        </p>
      </div>
      <div className="plan-panel-grid">
        <section className="project-surface plan-tasks">
          <div className="surface-heading">
            <div>
              <p className="eyebrow">This project</p>
              <h2>Tasks to schedule</h2>
            </div>
            <span className="count-chip">{schedulable.length}</span>
          </div>
          {open.length ? (
            <ul className="mini-task-list">
              {open.map((task) => {
                const ready = Boolean(
                  task.server && task.dueDate && task.estimate,
                );
                return (
                  <li key={task.id} className={!ready ? "needs-details" : ""}>
                    <input
                      type="checkbox"
                      aria-label={`Select ${task.title}`}
                      disabled={!ready}
                      checked={selected.includes(task.id)}
                      onChange={(event) =>
                        setSelected((current) =>
                          event.target.checked
                            ? [...current, task.id]
                            : current.filter((id) => id !== task.id),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="plan-task-content"
                      onClick={() => {
                        if (!ready) {
                          onEdit(task);
                          return;
                        }
                        setSelected((current) =>
                          current.includes(task.id)
                            ? current.filter((id) => id !== task.id)
                            : [...current, task.id],
                        );
                      }}
                    >
                      <strong>{task.title}</strong>
                      <time>
                        {task.estimate
                          ? `${task.estimate}m`
                          : "Estimate needed"}
                        {task.dueDate
                          ? ` · due ${task.dueDate}`
                          : " · due date needed"}
                      </time>
                    </button>
                    <button
                      type="button"
                      className="text-link plan-task-edit"
                      onClick={() => onEdit(task)}
                    >
                      {ready ? "Edit" : "Add details"}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="surface-empty">
              Add a few tasks and they’ll show up here, ready to schedule.
            </p>
          )}
        </section>
        <section className="project-surface plan-week">
          <div className="surface-heading">
            <div>
              <p className="eyebrow">This week</p>
              <h2>Weekly plan</h2>
            </div>
          </div>
          {result?.result?.sessions.length ? (
            <>
              <p className="calendar-help">
                Drag a block to move it, or select it to edit its date, time,
                and duration.
              </p>
              <WeeklyCalendar
                sessions={result.result.sessions}
                busyIntervals={result.setup!.busy_intervals}
                tasks={tasks}
                taskDeadlines={Object.fromEntries(
                  result.setup!.tasks.map((task) => [task.id, task.deadline]),
                )}
                taskEstimates={Object.fromEntries(
                  result.setup!.tasks.map((task) => [
                    task.id,
                    task.estimated_minutes,
                  ]),
                )}
                windowStart={result.setup!.window.start}
                windowEnd={result.setup!.window.end}
                preferences={{
                  earliest:
                    preferencesQuery.data?.earliest_study_time || "08:00",
                  latest: preferencesQuery.data?.latest_study_time || "22:00",
                  maximumSessionMinutes:
                    preferencesQuery.data?.maximum_session_minutes || 90,
                  minimumBreakMinutes:
                    preferencesQuery.data?.minimum_break_minutes || 0,
                }}
                saving={adjustSessions.isPending}
                onMove={(key, start) => updateSession(key, start)}
                onEdit={setEditingSession}
                onInvalid={setPlacementError}
              />
              {placementError && (
                <p className="calendar-drop-error" role="alert">
                  {placementError}
                </p>
              )}
            </>
          ) : (
            <div className="plan-week-placeholder">
              <p>
                Your proposed time blocks will appear here before anything is
                added.
              </p>
            </div>
          )}
          <ErrorMessage
            error={generate.error || adjustSessions.error}
            title={
              adjustSessions.error
                ? "We couldn’t update that time block."
                : "We couldn’t build this plan."
            }
          />
          <div
            className={`calendar-readiness ${calendarId ? "ready" : "setup"}`}
          >
            <CalendarDays />
            {connectionQuery.isPending ? (
              <div>
                <strong>Checking Google Calendar</strong>
                <p>Confirming the destination for this plan.</p>
              </div>
            ) : calendarId ? (
              <div>
                <strong>Google Calendar ready</strong>
                <p>Time blocks will be added to {calendarSummary}.</p>
              </div>
            ) : googleConnection ? (
              <div className="calendar-picker-inline">
                <div>
                  <strong>Select a destination calendar</strong>
                  <p>
                    Relay needs this to check conflicts and add time blocks.
                  </p>
                </div>
                <select
                  aria-label="Google Calendar destination"
                  value={calendarChoice}
                  onChange={(event) => setCalendarChoice(event.target.value)}
                >
                  <option value="">Choose a calendar</option>
                  {(googleCalendars.data || []).map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.summary}
                    </option>
                  ))}
                </select>
                <button
                  className="button secondary"
                  disabled={!calendarChoice || selectCalendar.isPending}
                  onClick={() => selectCalendar.mutate()}
                >
                  Use calendar
                </button>
                {!googleCalendars.data?.length && (
                  <button
                    className="text-link"
                    disabled={refreshCalendars.isPending}
                    onClick={() => refreshCalendars.mutate()}
                  >
                    Refresh calendars
                  </button>
                )}
              </div>
            ) : (
              <div>
                <strong>Google Calendar isn’t connected</strong>
                <p>Connect it to check conflicts and add this weekly plan.</p>
                <Link className="text-link" href="/connections">
                  Connect Google Calendar
                </Link>
              </div>
            )}
          </div>
          <ErrorMessage
            error={
              addToCalendar.error ||
              connectionQuery.error ||
              selectCalendar.error ||
              refreshCalendars.error ||
              googleCalendars.error
            }
            title={
              addToCalendar.error
                ? "Google Calendar couldn’t be updated."
                : "Google Calendar needs attention."
            }
          />
          {addToCalendar.isSuccess && (
            <p className="success-message">Added to Google Calendar</p>
          )}
          <p className="plan-selection-hint">
            {selected.length
              ? `${selected.length} ${selected.length === 1 ? "task" : "tasks"} selected for this schedule.`
              : "Select one or more tasks on the left to create a schedule."}
          </p>
          <div className="plan-actions">
            <Link className="button secondary" href="/settings">
              Adjust preferences
            </Link>
            <button
              className="button plan-generate-button"
              disabled={
                !selected.length ||
                !calendarId ||
                connectionQuery.isPending ||
                generate.isPending
              }
              onClick={() => {
                if (
                  addToCalendar.isSuccess &&
                  typeof window !== "undefined" &&
                  !window.confirm(
                    "This plan was already added to Google Calendar. Rebuilding will create a new plan without changing those calendar events. Continue?",
                  )
                ) {
                  return;
                }
                addToCalendar.reset();
                generate.mutate();
              }}
            >
              {generate.isPending ? (
                <Spinner label="Generating project schedule" />
              ) : (
                <Sparkles />
              )}
              {generate.isPending
                ? "Creating schedule…"
                : !selected.length
                  ? "Select tasks to create schedule"
                  : result
                    ? `Rebuild schedule (${selected.length})`
                    : `Create schedule (${selected.length})`}
            </button>
            {result?.result?.sessions.length ? (
              <button
                className="button"
                disabled={
                  !calendarId ||
                  addToCalendar.isPending ||
                  addToCalendar.isSuccess
                }
                onClick={() => addToCalendar.mutate()}
                aria-busy={addToCalendar.isPending}
              >
                {addToCalendar.isPending ? (
                  <Spinner label="Adding schedule to Google Calendar" />
                ) : (
                  <CalendarDays />
                )}
                {addToCalendar.isPending
                  ? "Adding to Google Calendar…"
                  : "Add to Google Calendar"}
              </button>
            ) : null}
          </div>
        </section>
      </div>
      {editingSession && (
        <ScheduleBlockModal
          key={sessionKey(editingSession)}
          session={editingSession}
          title={taskTitle(editingSession.task_id)}
          windowStart={result!.setup!.window.start}
          windowEnd={result!.setup!.window.end}
          pending={adjustSessions.isPending}
          close={() => setEditingSession(null)}
          save={(start, duration) =>
            updateSession(sessionKey(editingSession), start, duration)
          }
        />
      )}
    </section>
  );
}

function SourcesView({
  projectId,
  project,
}: {
  projectId: string;
  project: {
    notion_database_id: string | null;
    github_repository_owner: string | null;
    github_repository_name: string | null;
  };
}) {
  const captured = useProjectSources(projectId);
  const connected = [
    project.notion_database_id && {
      id: "notion",
      title: "Notion workspace",
      source_type: "Connected source",
      status: "READY",
    },
    project.github_repository_owner &&
      project.github_repository_name && {
        id: "github",
        title: `${project.github_repository_owner}/${project.github_repository_name}`,
        source_type: "GitHub repository",
        status: "READY",
      },
  ].filter(Boolean) as {
    id: string;
    title: string;
    source_type: string;
    status: string;
  }[];
  const sources = [...(captured.data || []), ...connected];
  return (
    <section className="project-surface source-surface">
      <div className="surface-heading">
        <div>
          <p className="eyebrow">Reference material</p>
          <h2>Sources</h2>
        </div>
      </div>
      {sources.length ? (
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.id}>
              <span>
                <FileText />
              </span>
              <div>
                <strong>{source.title}</strong>
                <p>
                  {source.source_type.replaceAll("_", " ").toLowerCase()} ·{" "}
                  {source.status.toLowerCase()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No sources added.">
          Use the project Add menu to bring in a brief, notes, or another
          starting point.
        </Empty>
      )}
    </section>
  );
}
