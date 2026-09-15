"use client";

import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, CalendarDays, FolderHeart, GraduationCap, Inbox, Sparkles } from "lucide-react";
import { usePendingApprovals, useProjects, useUser } from "@/hooks/queries";
import { ErrorMessage, Loading } from "@/components/ui";
import { ProjectCard } from "@/components/project-card";
import { NewProjectButton } from "@/components/project-library";
import { useProjectTasks } from "@/lib/project-tasks";

const spaces = [
  { slug: "school", name: "School", icon: GraduationCap },
  { slug: "work", name: "Work", icon: BriefcaseBusiness },
  { slug: "personal", name: "Personal", icon: FolderHeart },
] as const;

export default function Dashboard() {
  const user = useUser();
  const projects = useProjects();
  const approvals = usePendingApprovals();
  const tasks = useProjectTasks();
  if (user.isPending || projects.isPending || approvals.isPending) return <Loading />;
  const error = user.error || projects.error || approvals.error;
  if (error) return <ErrorMessage error={error} />;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const todayKey = new Date().toISOString().slice(0, 10);
  const today = tasks.filter((task) => task.status !== "DONE" && task.dueDate && task.dueDate <= todayKey);
  return (
    <>
      <header className="home-hero">
        <div><p className="eyebrow">Your workspace</p><h1>{greeting}, {user.data?.name.split(" ")[0]}.</h1><p>Here’s what you’re working on.</p></div>
        <NewProjectButton initialSpace="SCHOOL" />
      </header>
      {!user.data?.onboarding_completed && <p className="notice mb-8">Make Relay yours. <Link className="underline" href="/onboarding">Finish your setup</Link></p>}
      <section className="space-switcher" aria-label="Spaces">
        {spaces.map(({ slug, name, icon: Icon }) => <Link key={slug} href={`/spaces/${slug}`} className={slug}><span><Icon /></span><div><strong>{name}</strong><small>{(projects.data || []).filter((project) => project.space === slug.toUpperCase()).length} projects</small></div><ArrowRight /></Link>)}
      </section>
      <section className="home-section">
        <div className="product-section-heading"><div><p className="eyebrow">Pick up where you left off</p><h2>Recent projects</h2></div>{(projects.data || []).length > 0 && <Link className="text-link" href="/spaces/school">View spaces</Link>}</div>
        {(projects.data || []).length ? <div className="project-carousel">{projects.data?.slice(0, 8).map((project) => { const projectTasks = tasks.filter((task) => task.projectId === project.id); return <ProjectCard key={project.id} project={project} taskCount={projectTasks.length} doneCount={projectTasks.filter((task) => task.status === "DONE").length} />; })}</div> : <div className="home-empty"><Sparkles /><div><h3>Your next project starts here.</h3><p>Create a project in School, Work, or Personal to keep its tasks and sources together.</p></div></div>}
      </section>
      <div className="home-lower-grid">
        <section className="home-panel"><div className="panel-title"><span className="panel-icon blue"><CalendarDays /></span><div><h2>Today</h2><p>Tasks that need your focus now.</p></div><Link href="/my-day">Open My Day <ArrowRight /></Link></div>{today.length ? <ul className="mini-task-list">{today.slice(0, 4).map((task) => <li key={task.id}><span /><strong>{task.title}</strong><time>{task.dueDate === todayKey ? "Today" : "Overdue"}</time></li>)}</ul> : <p className="panel-empty">Nothing due today. A little breathing room.</p>}</section>
        <section className="home-panel"><div className="panel-title"><span className="panel-icon coral"><Inbox /></span><div><h2>Needs attention</h2><p>Proposals waiting for your review.</p></div><Link href="/inbox">Open inbox <ArrowRight /></Link></div>{approvals.data?.length ? <div className="attention-count"><strong>{approvals.data.length}</strong><span>{approvals.data.length === 1 ? "item is" : "items are"} ready to review</span></div> : <p className="panel-empty">You’re all caught up.</p>}</section>
      </div>
    </>
  );
}
