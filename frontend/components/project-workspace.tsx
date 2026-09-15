"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, Circle, Clock3, FileText, ListTodo, MoreHorizontal, Plus, Sparkles, Trash2, X } from "lucide-react";
import { useProject } from "@/hooks/queries";
import { Empty, ErrorMessage, Loading } from "@/components/ui";
import { readTasks, useProjectTasks, writeTasks, type ProjectTask } from "@/lib/project-tasks";
import { SourceCaptureModal } from "@/components/source-capture-modal";
import { projects, type Project } from "@/features/projects/api";
import type { SourceType } from "@/features/sources/api";
import { useProjectSources, useServerTasks } from "@/hooks/queries";
import { localDateValue } from "@/lib/datetime";

const tabs = ["overview", "tasks", "plan", "sources"] as const;
type Tab = (typeof tabs)[number];
const statusLabels = { TODO: "Todo", IN_PROGRESS: "In progress", DONE: "Done" } as const;
const addOptions = {
  SCHOOL: [["Assignment / brief", "ASSIGNMENT_BRIEF"], ["Course outline", "COURSE_OUTLINE"], ["Study goal", "STUDY_GOAL"]],
  WORK: [["Meeting notes / transcript", "MEETING_TRANSCRIPT"], ["Document / brief", "DOCUMENT_BRIEF"]],
  PERSONAL: [["Goal / project idea", "PERSONAL_GOAL"], ["Notes / checklist", "NOTES_CHECKLIST"]],
} as const;

function TaskModal({ projectId, close, save }: { projectId: string; close: () => void; save: (task: ProjectTask) => void }) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [estimate, setEstimate] = useState("");
  const [priority, setPriority] = useState<ProjectTask["priority"]>("MEDIUM");
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <section className="project-modal compact" role="dialog" aria-modal="true" aria-labelledby="task-title">
        <div className="modal-heading"><div><p className="eyebrow">Quick add</p><h2 id="task-title">New task</h2></div><button className="icon-button" onClick={close} aria-label="Close"><X /></button></div>
        <form onSubmit={(event) => { event.preventDefault(); save({ id: crypto.randomUUID(), projectId, title: title.trim(), status: "TODO", priority, dueDate: dueDate || null, estimate: estimate ? Number(estimate) : null }); }}>
          <label className="field">Task title<input autoFocus required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="What needs doing?" /></label>
          <div className="form-split">
            <label className="field">Due date <span className="optional">Optional</span><input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label>
            <label className="field">Estimate <span className="optional">Minutes</span><input type="number" min={5} step={5} value={estimate} onChange={(event) => setEstimate(event.target.value)} /></label>
          </div>
          <label className="field">Priority<select value={priority} onChange={(event) => setPriority(event.target.value as ProjectTask["priority"])}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option></select></label>
          <div className="modal-actions"><button type="button" className="button secondary" onClick={close}>Cancel</button><button className="button" disabled={!title.trim()}>Add task</button></div>
        </form>
      </section>
    </div>
  );
}

function DeleteProjectModal({ name, close, confirm, pending, error }: { name: string; close: () => void; confirm: () => void; pending: boolean; error: unknown }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <section className="project-modal compact" role="dialog" aria-modal="true" aria-labelledby="delete-project-title">
        <div className="modal-heading"><div><p className="eyebrow">This can’t be undone</p><h2 id="delete-project-title">Delete “{name}”?</h2></div><button className="icon-button" onClick={close} aria-label="Close"><X /></button></div>
        <p className="modal-body-text">This permanently removes its tasks, sources, and pending proposals.</p>
        <ErrorMessage error={error} title="Couldn’t delete this project" />
        <div className="modal-actions"><button type="button" className="button secondary" onClick={close} disabled={pending}>Cancel</button><button type="button" className="button reject-button" onClick={confirm} disabled={pending}>{pending ? "Deleting…" : "Delete project"}</button></div>
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
  const [tab, setTab] = useState<Tab>(tabs.includes(requestedTab as Tab) ? requestedTab as Tab : "overview");
  const allTasks = useProjectTasks();
  const serverTasks = useServerTasks(id);
  const remoteTasks: ProjectTask[] = (serverTasks.data || []).map((task) => ({
    id: task.id, projectId: task.project_id, title: task.title, status: task.status,
    priority: task.priority || "MEDIUM", dueDate: task.due_date ? localDateValue(task.due_date) : null,
    estimate: task.estimate_minutes, sourceTitle: task.source_title,
    sourceReference: task.source_reference, server: true,
  }));
  const tasks = [...remoteTasks, ...allTasks.filter((task) => task.projectId === id)];
  const [addingTask, setAddingTask] = useState(false);
  const [addingSource, setAddingSource] = useState<SourceType | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const chooseTab = (next: Tab) => { setTab(next); router.replace(`/projects/${id}?tab=${next}`, { scroll: false }); };
  const persist = (nextProjectTasks: ProjectTask[]) => {
    const all = readTasks().filter((task) => task.projectId !== id);
    writeTasks([...all, ...nextProjectTasks.filter((task) => !task.server)]);
  };
  const deleteProject = useMutation({
    mutationFn: () => projects.delete(id),
    onSuccess: () => {
      cache.setQueryData<Project[]>(["projects"], (current = []) => current.filter((p) => p.id !== id));
      router.replace(`/spaces/${(project.data?.space || "personal").toLowerCase()}`);
    },
  });
  if (project.isPending) return <Loading label="Loading project" />;
  if (project.error || !project.data) return <ErrorMessage error={project.error || new Error("Project not found.")} />;
  const item = project.data;
  const done = tasks.filter((task) => task.status === "DONE").length;
  const progress = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
  return (
    <>
      <Link className="project-back" href={`/spaces/${item.space.toLowerCase()}`}>← {item.space.toLowerCase()}</Link>
      <header className="project-header">
        <div><div className={`space-chip ${item.space.toLowerCase()}`}>{item.space.toLowerCase()}</div><h1>{item.name}</h1><div className="project-header-meta">{item.deadline && <span><CalendarDays /> Due {new Date(item.deadline).toLocaleDateString(undefined, { month: "long", day: "numeric" })}</span>}<span><CheckCircle2 /> {tasks.length ? `${progress}% complete` : "No tasks yet"}</span></div></div>
        <div className="project-header-actions">
          <details className="add-menu"><summary className="button"><Plus /> Add</summary><div className="add-popover"><button onClick={() => setAddingTask(true)}><ListTodo />Task</button>{addOptions[item.space].map(([label, sourceType]) => <button key={label} onClick={() => setAddingSource(sourceType)}><FileText />{label}</button>)}</div></details>
          <button className="icon-button" onClick={() => setConfirmingDelete(true)} aria-label="Delete project" title="Delete project"><Trash2 /></button>
        </div>
      </header>
      <nav className="project-tabs" aria-label="Project sections">{tabs.map((value) => <button key={value} className={tab === value ? "active" : ""} aria-current={tab === value ? "page" : undefined} onClick={() => chooseTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</nav>
      {tab === "overview" && <Overview description={item.description} tasks={tasks} deadline={item.deadline} onAdd={() => setAddingTask(true)} onTab={chooseTab} />}
      {tab === "tasks" && <TaskView tasks={tasks} update={persist} onAdd={() => setAddingTask(true)} />}
      {tab === "plan" && <PlanView tasks={tasks} />}
      {tab === "sources" && <SourcesView projectId={id} project={item} />}
      {addingTask && <TaskModal projectId={id} close={() => setAddingTask(false)} save={(task) => { persist([...tasks, task]); setAddingTask(false); setTab("tasks"); }} />}
      {addingSource && <SourceCaptureModal projectId={id} sourceType={addingSource} close={() => setAddingSource(null)} />}
      {confirmingDelete && <DeleteProjectModal name={item.name} close={() => setConfirmingDelete(false)} confirm={() => deleteProject.mutate()} pending={deleteProject.isPending} error={deleteProject.error} />}
    </>
  );
}

function Overview({ description, tasks, deadline, onAdd, onTab }: { description: string | null; tasks: ProjectTask[]; deadline: string | null; onAdd: () => void; onTab: (tab: Tab) => void }) {
  const open = tasks.filter((task) => task.status !== "DONE");
  return <div className="overview-grid"><section className="project-surface overview-main"><p className="eyebrow">Project goal</p><h2>{description || "Give this project a clear next step."}</h2><p>{description ? "Keep momentum by choosing the next useful task." : "Add tasks now; richer project editing will arrive in a later phase."}</p><button className="button secondary" onClick={onAdd}><Plus /> Add a task</button></section><aside className="project-surface snapshot"><h2>At a glance</h2><dl><div><dt>Open tasks</dt><dd>{open.length}</dd></div><div><dt>Completed</dt><dd>{tasks.length ? `${Math.round(((tasks.length - open.length) / tasks.length) * 100)}%` : "—"}</dd></div><div><dt>Deadline</dt><dd>{deadline ? new Date(deadline).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "Not set"}</dd></div></dl></aside><section className="project-surface next-tasks"><div className="surface-heading"><div><p className="eyebrow">Next up</p><h2>Open tasks</h2></div><button className="text-link" onClick={() => onTab("tasks")}>View all</button></div>{open.length ? <ul>{open.slice(0, 3).map((task) => <li key={task.id}><Circle /><span>{task.title}</span>{task.dueDate && <time>{new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time>}</li>)}</ul> : <p className="surface-empty">Nothing queued yet. Add the first small step.</p>}</section></div>;
}

function TaskView({ tasks, update, onAdd }: { tasks: ProjectTask[]; update: (tasks: ProjectTask[]) => void; onAdd: () => void }) {
  const change = (id: string, status: ProjectTask["status"]) => {
    if (tasks.find((task) => task.id === id)?.server) return;
    update(tasks.map((task) => task.id === id ? { ...task, status } : task));
  };
  return <section className="project-surface task-surface"><div className="surface-heading"><div><p className="eyebrow">Simple and focused</p><h2>Tasks</h2></div><button className="button secondary" onClick={onAdd}><Plus /> Add task</button></div>{tasks.length ? <div className="task-groups">{(["TODO", "IN_PROGRESS", "DONE"] as const).map((status) => <section key={status} className="task-group"><div className="task-group-title"><h3>{statusLabels[status]}</h3><span>{tasks.filter((task) => task.status === status).length}</span></div>{tasks.filter((task) => task.status === status).map((task) => <article className="task-row" key={task.id}><button aria-label={`Move ${task.title} forward`} onClick={() => change(task.id, status === "TODO" ? "IN_PROGRESS" : status === "IN_PROGRESS" ? "DONE" : "TODO")}>{status === "DONE" ? <CheckCircle2 /> : <Circle />}</button><div><strong>{task.title}</strong><p><span className={`priority ${task.priority.toLowerCase()}`}>{task.priority.toLowerCase()}</span>{task.estimate && <span><Clock3 /> {task.estimate}m</span>}{task.dueDate && <span><CalendarDays /> {new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>}{task.sourceTitle && <span className="task-source">From {task.sourceTitle}{task.sourceReference ? ` · ${task.sourceReference}` : ""}</span>}</p></div><MoreHorizontal /></article>)}</section>)}</div> : <Empty title="No tasks yet.">Add a first task to turn this project into a plan.</Empty>}</section>;
}

function PlanView({ tasks }: { tasks: ProjectTask[] }) {
  const open = tasks.filter((task) => task.status !== "DONE");
  return (
    <section className="plan-panel">
      <div className="plan-panel-intro"><p className="eyebrow">Plan</p><h2>Plan your project</h2><p>Turn your project tasks into focused time blocks around your existing schedule.</p></div>
      <div className="plan-panel-grid">
        <section className="project-surface plan-tasks">
          <div className="surface-heading"><div><p className="eyebrow">This project</p><h2>Tasks to schedule</h2></div><span className="count-chip">{open.length}</span></div>
          {open.length ? <ul className="mini-task-list">{open.slice(0, 6).map((task) => <li key={task.id}><span /><strong>{task.title}</strong>{task.estimate ? <time>{task.estimate}m</time> : task.dueDate ? <time>{new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time> : null}</li>)}</ul> : <p className="surface-empty">Add a few tasks and they’ll show up here, ready to schedule.</p>}
        </section>
        <section className="project-surface plan-week">
          <div className="surface-heading"><div><p className="eyebrow">This week</p><h2>Weekly plan</h2></div></div>
          <div className="calendar-shell"><div><span>9 AM</span><i /></div><div><span>12 PM</span><i /></div><div><span>3 PM</span><i /></div><p>Your scheduled work will appear here.</p></div>
          <button className="button secondary plan-week-cta" disabled title="Coming soon"><Sparkles /> Plan my week</button>
        </section>
      </div>
    </section>
  );
}

function SourcesView({ projectId, project }: { projectId: string; project: { notion_database_id: string | null; github_repository_owner: string | null; github_repository_name: string | null } }) {
  const captured = useProjectSources(projectId);
  const connected = [project.notion_database_id && { id: "notion", title: "Notion workspace", source_type: "Connected source", status: "READY" }, project.github_repository_owner && project.github_repository_name && { id: "github", title: `${project.github_repository_owner}/${project.github_repository_name}`, source_type: "GitHub repository", status: "READY" }].filter(Boolean) as { id: string; title: string; source_type: string; status: string }[];
  const sources = [...(captured.data || []), ...connected];
  return <section className="project-surface source-surface"><div className="surface-heading"><div><p className="eyebrow">Reference material</p><h2>Sources</h2></div></div>{sources.length ? <ul className="source-list">{sources.map((source) => <li key={source.id}><span><FileText /></span><div><strong>{source.title}</strong><p>{source.source_type.replaceAll("_", " ").toLowerCase()} · {source.status.toLowerCase()}</p></div></li>)}</ul> : <Empty title="No sources added.">Use the project Add menu to bring in a brief, notes, or another starting point.</Empty>}</section>;
}
