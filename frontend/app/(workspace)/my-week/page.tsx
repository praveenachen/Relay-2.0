"use client";

import Link from "next/link";
import {
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  Sparkles,
} from "lucide-react";
import { useAllServerTasks, useProjects } from "@/hooks/queries";
import { ErrorMessage, Loading } from "@/components/ui";
import {
  projectTaskFromServer,
  useProjectTasks,
  writeTasks,
} from "@/lib/project-tasks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { relaySchedule } from "@/features/plan/api";
import { sources } from "@/features/sources/api";

function startOfWeek(date: Date) {
  const day = new Date(date);
  day.setHours(0, 0, 0, 0);
  return day;
}

function weekKeys(from: Date) {
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(from);
    day.setDate(from.getDate() + index);
    return day.toISOString().slice(0, 10);
  });
}

export default function MyWeek() {
  const projects = useProjects();
  const cache = useQueryClient();
  const serverTasks = useAllServerTasks();
  const schedule = useQuery({
    queryKey: ["schedule"],
    queryFn: relaySchedule.list,
  });
  const localTasks = useProjectTasks();
  const tasks = [
    ...(serverTasks.data || []).map(projectTaskFromServer),
    ...localTasks,
  ];
  const updateServerTask = useMutation({
    mutationFn: (task: (typeof tasks)[number]) =>
      sources.updateTask(task.projectId, task.id, {
        title: task.title,
        description: task.description,
        due_date: task.dueDate ? `${task.dueDate}T23:59:00Z` : null,
        estimate_minutes: task.estimate,
        priority: task.priority,
        status: task.status,
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["tasks"] }),
  });
  if (projects.isPending || serverTasks.isPending) return <Loading />;
  if (projects.error || serverTasks.error)
    return <ErrorMessage error={projects.error || serverTasks.error} />;
  const today = new Date();
  const key = today.toISOString().slice(0, 10);
  const weekStart = startOfWeek(today);
  const days = weekKeys(weekStart);
  const weekEnd = days[days.length - 1];
  const due = tasks.filter(
    (task) => task.status !== "DONE" && task.dueDate && task.dueDate <= key,
  );
  const dueThisWeek = tasks.filter(
    (task) =>
      task.status !== "DONE" &&
      task.dueDate &&
      task.dueDate > key &&
      task.dueDate <= weekEnd,
  );
  const upcoming = tasks.filter(
    (task) =>
      task.status !== "DONE" && (!task.dueDate || task.dueDate > weekEnd),
  );
  const toggle = (id: string) => {
    const current = tasks.find((task) => task.id === id);
    if (current?.server) {
      updateServerTask.mutate({
        ...current,
        status: current.status === "DONE" ? "TODO" : "DONE",
      });
      return;
    }
    const next = tasks.map((task) =>
      task.id === id
        ? {
            ...task,
            status:
              task.status === "DONE" ? ("TODO" as const) : ("DONE" as const),
          }
        : task,
    );
    writeTasks(next.filter((task) => !task.server));
  };
  const projectName = (id: string) =>
    projects.data?.find((project) => project.id === id)?.name || "Project";
  return (
    <>
      <header className="day-hero">
        <div>
          <p className="eyebrow">
            {weekStart.toLocaleDateString(undefined, {
              month: "long",
              day: "numeric",
            })}{" "}
            –{" "}
            {new Date(weekEnd).toLocaleDateString(undefined, {
              month: "long",
              day: "numeric",
            })}
          </p>
          <h1>My Week</h1>
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
              <h2>This week</h2>
            </div>
            <CalendarDays />
          </div>
          <div className="calendar-shell">
            {days.map((day) => {
              const blocksForDay = (schedule.data || []).filter(
                (block) => block.start.slice(0, 10) === day,
              );
              const dueForDay = dueThisWeek.filter(
                (task) => task.dueDate === day,
              );
              if (!blocksForDay.length && !dueForDay.length) return null;
              return (
                <div key={day} className="week-day-group">
                  <p className="eyebrow">
                    {new Date(`${day}T12:00:00`).toLocaleDateString(undefined, {
                      weekday: "long",
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                  {blocksForDay.map((block) => (
                    <article
                      key={`${block.run_id}-${block.task_id}-${block.start}`}
                    >
                      <strong>{block.task_title}</strong>
                      <small>{block.project_name}</small>
                      <time>
                        {new Date(block.start).toLocaleTimeString(undefined, {
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </time>
                    </article>
                  ))}
                  {dueForDay.map((task) => (
                    <article key={task.id}>
                      <strong>{task.title}</strong>
                      <small>{projectName(task.projectId)} · due</small>
                    </article>
                  ))}
                </div>
              );
            })}
            {!schedule.isPending &&
              !(schedule.data || []).some((block) =>
                days.includes(block.start.slice(0, 10)),
              ) &&
              !dueThisWeek.length && (
                <p>No Relay time blocks scheduled this week.</p>
              )}
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
