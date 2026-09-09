"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useUser } from "@/hooks/queries";
import { auth } from "@/features/auth/api";
import { ErrorMessage } from "@/components/ui";

export function WorkspaceNav({ name }: { name: string }) {
  const path = usePathname();
  const user = useUser();
  const router = useRouter();
  const cache = useQueryClient();
  const logout = useMutation({
    mutationFn: auth.logout,
    onSuccess: () => {
      cache.clear();
      router.replace("/login");
      router.refresh();
    },
  });
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-5 px-6 py-5">
        <Link
          href="/dashboard"
          className="mr-5 text-2xl font-semibold tracking-tight"
        >
          ↗ relay
        </Link>
        <nav aria-label="Workspace" className="flex flex-wrap gap-1">
          {[
            ["/dashboard", "Overview"],
            ["/runs", "Runs"],
            ["/approvals", "Approvals"],
            ["/connections", "Connections"],
            ["/settings", "Settings"],
          ].map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={path === href ? "page" : undefined}
              className={`rounded-lg px-3 py-2 text-sm ${path === href ? "bg-background font-semibold text-accent" : "text-muted"}`}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm">
          <span>{user.data?.name || name}</span>
          <button
            className="text-muted underline underline-offset-4"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            Sign out
          </button>
        </div>
        <ErrorMessage error={logout.error} />
      </div>
    </header>
  );
}
