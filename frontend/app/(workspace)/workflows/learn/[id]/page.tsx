import { LearnRun } from "@/components/learn-workflow";

export default async function LearnRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <LearnRun id={id} />;
}
