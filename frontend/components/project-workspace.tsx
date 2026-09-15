"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { CalendarDays, CheckCircle2, Circle, Clock3, FileText, ListTodo, MoreHorizontal, Plus, Sparkles, X } from "lucide-react";
import { useProject } from "@/hooks/queries";
import { Empty, ErrorMessage, Loading } from "@/components/ui";
import { readTasks, useProjectTasks, writeTasks, type ProjectTask } from "@/lib/project-tasks";

const tabs = ["overview", "tasks", "plan", "sources"] as const;
type Tab = (typeof tabs)[number];
const statusLabels = { TODO: "Todo", IN_PROGRESS: "In progress", DONE: "Done" } as const;
const addOptions = {
  SCHOOL: [["Assignment / brief", "/workflows/learn"], ["Course outline", "/workflows/learn"], ["Study goal", "/workflows/plan"]],
  WORK: [["Meeting notes / transcript", "/workflows/collaborate"], ["Document / brief", "/workflows/learn"], ["GitHub issue / link", "/connections"]],
  PERSONAL: [["Goal / project idea", "/workflows/plan"], ["Notes / checklist", "/workflows/learn"]],
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

export function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const project = useProject(id);
  const requestedTab = search.get("tab")?.toLowerCase();
  const [tab, setTab] = useState<Tab>(tabs.includes(requestedTab as Tab) ? requestedTab as Tab : "overview");
  const allTasks = useProjectTasks();
  const tasks = allTasks.filter((task) => task.projectId === id);
  const [addingTask, setAddingTask] = useState(false);
  const chooseTab = (next: Tab) => { setTab(next); router.replace(`/projects/${id}?tab=${next}`, { scroll: false }); };
  const persist = (nextProjectTasks: ProjectTask[]) => {
    const all = readTasks().filter((task) => task.projectId !== id);
    writeTasks([...all, ...nextProjectTasks]);
  };
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
        <details className="add-menu"><summary className="button"><Plus /> Add</summary><div className="add-popover"><button onClick={() => setAddingTask(true)}><ListTodo />Task</button>{addOptions[item.space].map(([label, href]) => <Link key={label} href={href}><FileText />{label}</Link>)}</div></details>
      </header>
      <nav className="project-tabs" aria-label="Project sections">{tabs.map((value) => <button key={value} className={tab === value ? "active" : ""} aria-current={tab === value ? "page" : undefined} onClick={() => chooseTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</nav>
      {tab === "overview" && <Overview description={item.description} tasks={tasks} deadline={item.deadline} onAdd={() => setAddingTask(true)} onTab={chooseTab} />}
      {tab === "tasks" && <TaskView tasks={tasks} update={persist} onAdd={() => setAddingTask(true)} />}
      {tab === "plan" && <PlanView taskCount={tasks.filter((task) => task.status !== "DONE").length} />}
      {tab === "sources" && <SourcesView project={item} />}
      {addingTask && <TaskModal projectId={id} close={() => setAddingTask(false)} save={(task) => { persist([...tasks, task]); setAddingTask(false); setTab("tasks"); }} />}
    </>
  );
}

function Overview({ description, tasks, deadline, onAdd, onTab }: { description: string | null; tasks: ProjectTask[]; deadline: string | null; onAdd: () => void; onTab: (tab: Tab) => void }) {
  const open = tasks.filter((task) => task.status !== "DONE");
  return <div className="overview-grid"><section className="project-surface overview-main"><p className="eyebrow">Project goal</p><h2>{description || "Give this project a clear next step."}</h2><p>{description ? "Keep momentum by choosing the next useful task." : "Add tasks now; richer project editing will arrive in a later phase."}</p><button className="button secondary" onClick={onAdd}><Plus /> Add a task</button></section><aside className="project-surface snapshot"><h2>At a glance</h2><dl><div><dt>Open tasks</dt><dd>{open.length}</dd></div><div><dt>Completed</dt><dd>{tasks.length ? `${Math.round(((tasks.length - open.length) / tasks.length) * 100)}%` : "—"}</dd></div><div><dt>Deadline</dt><dd>{deadline ? new Date(deadline).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "Not set"}</dd></div></dl></aside><section className="project-surface next-tasks"><div className="surface-heading"><div><p className="eyebrow">Next up</p><h2>Open tasks</h2></div><button className="text-link" onClick={() => onTab("tasks")}>View all</button></div>{open.length ? <ul>{open.slice(0, 3).map((task) => <li key={task.id}><Circle /><span>{task.title}</span>{task.dueDate && <time>{new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time>}</li>)}</ul> : <p className="surface-empty">Nothing queued yet. Add the first small step.</p>}</section></div>;
}

function TaskView({ tasks, update, onAdd }: { tasks: ProjectTask[]; update: (tasks: ProjectTask[]) => void; onAdd: () => void }) {
  const change = (id: string, status: ProjectTask["status"]) => update(tasks.map((task) => task.id === id ? { ...task, status } : task));
  return <section className="project-surface task-surface"><div className="surface-heading"><div><p className="eyebrow">Simple and focused</p><h2>Tasks</h2></div><button className="button secondary" onClick={onAdd}><Plus /> Add task</button></div>{tasks.length ? <div className="task-groups">{(["TODO", "IN_PROGRESS", "DONE"] as const).map((status) => <section key={status} className="task-group"><div className="task-group-title"><h3>{statusLabels[status]}</h3><span>{tasks.filter((task) => task.status === status).length}</span></div>{tasks.filter((task) => task.status === status).map((task) => <article className="task-row" key={task.id}><button aria-label={`Move ${task.title} forward`} onClick={() => change(task.id, status === "TODO" ? "IN_PROGRESS" : status === "IN_PROGRESS" ? "DONE" : "TODO")}>{status === "DONE" ? <CheckCircle2 /> : <Circle />}</button><div><strong>{task.title}</strong><p><span className={`priority ${task.priority.toLowerCase()}`}>{task.priority.toLowerCase()}</span>{task.estimate && <span><Clock3 /> {task.estimate}m</span>}{task.dueDate && <span><CalendarDays /> {new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>}</p></div><MoreHorizontal /></article>)}</section>)}</div> : <Empty title="No tasks yet.">Add a first task to turn this project into a plan.</Empty>}</section>;
}

function PlanView({ taskCount }: { taskCount: number }) {
  return <section className="project-surface feature-shell"><div className="feature-icon"><Sparkles /></div><p className="eyebrow">Plan</p><h2>Make time for what matters.</h2><p>{taskCount ? `You have ${taskCount} open ${taskCount === 1 ? "task" : "tasks"} ready to plan.` : "Add a few tasks, then shape them into a realistic study week."}</p><Link className="button" href="/workflows/plan">Open planner</Link><small>Your existing scheduling workflow remains available and unchanged.</small></section>;
}

function SourcesView({ project }: { project: { notion_database_id: string | null; github_repository_owner: string | null; github_repository_name: string | null } }) {
  const sources = [project.notion_database_id && { name: "Notion workspace", type: "Connected source" }, project.github_repository_owner && project.github_repository_name && { name: `${project.github_repository_owner}/${project.github_repository_name}`, type: "GitHub repository" }].filter(Boolean) as { name: string; type: string }[];
  return <section className="project-surface source-surface"><div className="surface-heading"><div><p className="eyebrow">Reference material</p><h2>Sources</h2></div></div>{sources.length ? <ul className="source-list">{sources.map((source) => <li key={source.name}><span><FileText /></span><div><strong>{source.name}</strong><p>{source.type}</p></div></li>)}</ul> : <Empty title="No sources added.">Use the project Add menu to bring in a brief, notes, or another starting point.</Empty>}</section>;
}
