import { notFound } from "next/navigation";
import { displayForSlug } from "@/features/workflows/display";
import { WorkflowEntry } from "@/components/workflow-entry";
export default async function WorkflowEntryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const display = displayForSlug(slug);
  if (!display) notFound();
  return <WorkflowEntry display={display} />;
}
