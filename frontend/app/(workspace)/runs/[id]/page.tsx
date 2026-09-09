import { notFound } from "next/navigation";
import { z } from "zod";
import { RunDetail } from "@/components/run-detail";
export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) notFound();
  return <RunDetail id={id} />;
}
