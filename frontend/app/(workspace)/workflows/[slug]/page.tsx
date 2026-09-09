import { notFound } from "next/navigation";
import { displayForSlug } from "@/features/workflows/display";
import { WorkflowEntry } from "@/components/workflow-entry";
import { LearnEntry } from "@/components/learn-workflow";
import { PlanEntry } from "@/components/plan-workflow";
import { CollaborateEntry } from "@/components/collaborate-workflow";
export default async function WorkflowEntryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (slug === "learn") return <LearnEntry />;
  if (slug === "plan") return <PlanEntry />;
  if (slug === "collaborate") return <CollaborateEntry />;
  const display = displayForSlug(slug);
  if (!display) notFound();
  return <WorkflowEntry display={display} />;
}
