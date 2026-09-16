"use client";

import Link from "next/link";
import {
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  Sparkles,
} from "lucide-react";
import { useProjects } from "@/hooks/queries";
import { ErrorMessage, Loading } from "@/components/ui";
import { useProjectTasks, writeTasks } from "@/lib/project-tasks";

export default function MyDay() {
  const projects = useProjects();
  const tasks = useProjectTasks();
  if (projects.isPending) return <Loading />;
  if (projects.error) return <ErrorMessage error={projects.error} />;
  const today = new Date();
  const key = today.toISOString().slice(0, 10);
  const due = tasks.filter(
    (task) => task.status !== "DONE" && task.dueDate && task.dueDate <= key,
  );
  const upcoming = tasks.filter(
    (task) => task.status !== "DONE" && (!task.dueDate || task.dueDate > key),
  );
  const toggle = (id: string) => {
    const next = tasks.map((task) =>
      task.id === id
        ? {
            ...task,
            status:
              task.status === "DONE" ? ("TODO" as const) : ("DONE" as const),
          }
        : task,
    );
    writeTasks(next);
  };
  const projectName = (id: string) =>
    projects.data?.find((project) => project.id === id)?.name || "Project";
  return (
    <>
      <header className="day-hero">
        <div>
          <p className="eyebrow">
            {today.toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
          <h1>My Day</h1>
          <p>A calm view of what deserves your attention.</p>
        </div>
        <div className="day-orbit">
          <Sparkles />
        </div>
      </header>
      <div className="day-layout">
        <section className="project-surface day-focus">
          <div className="surface-heading">
            <div>
              <p className="eyebrow">Focus</p>
              <h2>Due now</h2>
            </div>
            <span className="count-chip">{due.length}</span>
          </div>
          {due.length ? (
            <ul className="day-task-list">
              {due.map((task) => (
                <li key={task.id}>
                  <button
                    onClick={() => toggle(task.id)}
                    aria-label={`Complete ${task.title}`}
                  >
                    <Circle />
                  </button>
                  <div>
                    <strong>{task.title}</strong>
                    <Link href={`/projects/${task.projectId}?tab=tasks`}>
                      {projectName(task.projectId)}
                    </Link>
                  </div>
                  {task.estimate && (
                    <span>
                      <Clock3 />
                      {task.estimate}m
                    </span>
                  )}
                  <time className={task.dueDate! < key ? "overdue" : ""}>
                    {task.dueDate === key ? "Today" : "Overdue"}
                  </time>
                </li>
              ))}
            </ul>
          ) : (
            <div className="day-empty">
              <CheckCircle2 />
              <h3>Your day is clear.</h3>
              <p>Tasks due today will gather here automatically.</p>
            </div>
          )}
        </section>
        <aside className="project-surface day-calendar">
          <div className="surface-heading">
            <div>
              <p className="eyebrow">Schedule</p>
              <h2>Calendar</h2>
            </div>
            <CalendarDays />
          </div>
          <div className="calendar-shell">
            <div>
              <span>9 AM</span>
              <i />
            </div>
            <div>
              <span>12 PM</span>
              <i />
            </div>
            <div>
              <span>3 PM</span>
              <i />
            </div>
            <p>Calendar events will appear here when available.</p>
          </div>
        </aside>
      </div>
      {upcoming.length > 0 && (
        <section className="project-surface coming-up">
          <div className="surface-heading">
            <div>
              <p className="eyebrow">Ahead</p>
              <h2>Coming up</h2>
            </div>
          </div>
          <ul>
            {upcoming.slice(0, 5).map((task) => (
              <li key={task.id}>
                <span
                  className={`priority-dot ${task.priority.toLowerCase()}`}
                />
                <Link href={`/projects/${task.projectId}?tab=tasks`}>
                  <strong>{task.title}</strong>
                  <small>{projectName(task.projectId)}</small>
                </Link>
                <time>
                  {task.dueDate
                    ? new Date(`${task.dueDate}T12:00:00`).toLocaleDateString(
                        undefined,
                        { month: "short", day: "numeric" },
                      )
                    : "Unscheduled"}
                </time>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
