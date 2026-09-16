"use client";

import { useState } from "react";
import { Plus, Sparkles, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAllServerTasks, useProjects } from "@/hooks/queries";
import { projects, type Project } from "@/features/projects/api";
import { ErrorMessage, Loading, Spinner } from "@/components/ui";
import { ProjectCard } from "@/components/project-card";
import { projectTaskFromServer, useProjectTasks } from "@/lib/project-tasks";

export type Space = "SCHOOL" | "WORK" | "PERSONAL";

export function NewProjectButton({ initialSpace }: { initialSpace: Space }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [space, setSpace] = useState<Space>(initialSpace);
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const cache = useQueryClient();
  const create = useMutation({
    mutationFn: projects.create,
    onSuccess: (project) => {
      cache.setQueryData<Project[]>(["projects"], (current = []) => [
        project,
        ...current,
      ]);
      setOpen(false);
      setName("");
      setDescription("");
      setDeadline("");
    },
  });
  return (
    <>
      <button className="button add-button" onClick={() => setOpen(true)}>
        <Plus /> New project
      </button>
      {open && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && setOpen(false)
          }
        >
          <section
            className="project-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-project-title"
          >
            <div className="modal-heading">
              <div>
                <p className="eyebrow">A fresh start</p>
                <h2 id="new-project-title">Create a project</h2>
              </div>
              <button
                className="icon-button"
                onClick={() => setOpen(false)}
                aria-label="Close"
              >
                <X />
              </button>
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate({
                  name: name.trim(),
                  space,
                  description: description.trim() || null,
                  deadline: deadline
                    ? new Date(`${deadline}T12:00:00`).toISOString()
                    : null,
                });
              }}
            >
              <label className="field">
                Project name
                <input
                  autoFocus
                  required
                  maxLength={200}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. Biology final"
                />
              </label>
              <label className="field">
                Space
                <select
                  value={space}
                  onChange={(event) => setSpace(event.target.value as Space)}
                >
                  <option value="SCHOOL">School</option>
                  <option value="WORK">Work</option>
                  <option value="PERSONAL">Personal</option>
                </select>
              </label>
              <label className="field">
                Goal or description <span className="optional">Optional</span>
                <textarea
                  rows={3}
                  maxLength={2000}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What does done look like?"
                />
              </label>
              <label className="field">
                Deadline <span className="optional">Optional</span>
                <input
                  type="date"
                  value={deadline}
                  onChange={(event) => setDeadline(event.target.value)}
                />
              </label>
              <ErrorMessage error={create.error} />
              <div className="modal-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </button>
                <button
                  className="button"
                  disabled={!name.trim() || create.isPending}
                >
                  {create.isPending && <Spinner label="Creating project" />}
                  {create.isPending ? "Creating…" : "Create project"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}

const emptyStateCopy: Record<Space, { title: string; description: string }> = {
  SCHOOL: {
    title: "No school projects yet.",
    description:
      "Create a project for an exam, assignment, course, or team project.",
  },
  WORK: {
    title: "No work projects yet.",
    description:
      "Create a project for a sprint, deliverable, research initiative, or anything you're actively working on.",
  },
  PERSONAL: {
    title: "No personal projects yet.",
    description:
      "Create a project for a goal, trip, portfolio update, event, or anything you want to organize.",
  },
};

export function ProjectLibrary({ space }: { space: Space }) {
  const query = useProjects();
  const localTasks = useProjectTasks();
  const serverTasks = useAllServerTasks();
  const tasks = [
    ...(serverTasks.data || []).map(projectTaskFromServer),
    ...localTasks,
  ];
  if (query.isPending || serverTasks.isPending)
    return <Loading label="Loading projects" />;
  if (query.error || serverTasks.error)
    return (
      <ErrorMessage
        error={query.error || serverTasks.error}
        retry={() => {
          query.refetch();
          serverTasks.refetch();
        }}
      />
    );
  const items = (query.data || []).filter((project) => project.space === space);
  if (!items.length) {
    const copy = emptyStateCopy[space];
    return (
      <div className={`home-empty space-empty ${space.toLowerCase()}`}>
        <Sparkles />
        <div>
          <h3>{copy.title}</h3>
          <p>{copy.description}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="project-grid">
      {items.map((project) => {
        const projectTasks = tasks.filter(
          (task) => task.projectId === project.id,
        );
        return (
          <ProjectCard
            key={project.id}
            project={project}
            taskCount={projectTasks.length}
            doneCount={
              projectTasks.filter((task) => task.status === "DONE").length
            }
          />
        );
      })}
    </div>
  );
}

export const spaceDetails = {
  SCHOOL: {
    title: "School",
    description:
      "Courses, assignments, exams, and everything that gets you to the finish line.",
    icon: Sparkles,
  },
  WORK: {
    title: "Work",
    description:
      "Keep briefs, meetings, and meaningful next steps in one place.",
    icon: Sparkles,
  },
  PERSONAL: {
    title: "Personal",
    description: "Plans and ideas for the parts of life that are yours.",
    icon: Sparkles,
  },
} as const;
