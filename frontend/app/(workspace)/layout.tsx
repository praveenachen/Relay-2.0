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
      <main className="workspace-shell">{children}</main>
    </>
  );
}
