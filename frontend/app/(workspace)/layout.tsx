import { requireUser } from "@/lib/session";
import { WorkspaceNav } from "@/components/workspace-nav";
export default async function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  return (
    <>
      <WorkspaceNav name={user.name} />
      <main className="mx-auto max-w-6xl px-6 py-10 sm:py-14">{children}</main>
    </>
  );
}
