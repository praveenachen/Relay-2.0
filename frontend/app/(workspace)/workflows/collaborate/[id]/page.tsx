import { CollaborateRun } from "@/components/collaborate-workflow";

export default async function CollaborateRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CollaborateRun id={id} />;
}
