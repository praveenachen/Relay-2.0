import { PlanRun } from "@/components/plan-workflow";

export default async function PlanRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PlanRun id={id} />;
}
