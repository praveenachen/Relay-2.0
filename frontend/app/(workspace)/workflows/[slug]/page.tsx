import { notFound } from "next/navigation";
import { displayForSlug } from "@/features/workflows/display";
import { WorkflowEntry } from "@/components/workflow-entry";
import { LearnEntry } from "@/components/learn-workflow";
export default async function WorkflowEntryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (slug === "learn") return <LearnEntry />;
  const display = displayForSlug(slug);
  if (!display) notFound();
  return <WorkflowEntry display={display} />;
}
