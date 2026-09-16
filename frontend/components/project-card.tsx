import Link from "next/link";
import { ArrowUpRight, CalendarDays } from "lucide-react";
import type { Project } from "@/features/projects/api";

export function ProjectCard({
  project,
  taskCount = 0,
  doneCount = 0,
}: {
  project: Project;
  taskCount?: number;
  doneCount?: number;
}) {
  const progress = taskCount ? Math.round((doneCount / taskCount) * 100) : 0;
  return (
    <Link
      href={`/projects/${project.id}`}
      className={`project-card ${project.space.toLowerCase()}`}
    >
      <div className="project-card-top">
        <span className="space-chip">{project.space.toLowerCase()}</span>
        <ArrowUpRight />
      </div>
      <div>
        <h3>{project.name}</h3>
        {project.description && <p>{project.description}</p>}
      </div>
      <div className="project-card-meta">
        <div className="progress-row">
          <span>{taskCount ? `${progress}% complete` : "Ready to start"}</span>
          <span>
            {taskCount ? `${taskCount - doneCount} open` : "No tasks"}
          </span>
        </div>
        <div className="project-progress">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="project-date">
          <CalendarDays />
          {project.deadline
            ? `Due ${new Date(project.deadline).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
            : `Updated ${new Date(project.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`}
        </div>
      </div>
    </Link>
  );
}
