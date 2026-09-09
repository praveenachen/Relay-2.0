"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useUser } from "@/hooks/queries";
import { auth } from "@/features/auth/api";
import { ErrorMessage } from "@/components/ui";
import { workflows } from "@/features/workflows/display";

const primaryLinks = [
  ["/dashboard", "Overview"],
  ...workflows.map(
    (workflow) => [`/workflows/${workflow.slug}`, workflow.title] as const,
  ),
  ["/approvals", "Approvals"],
  ["/runs", "History"],
];
const secondaryLinks = [
  ["/connections", "Connections"],
  ["/settings", "Settings"],
];

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
          {primaryLinks.map(([href, label]) => {
            const active =
              path === href ||
              (href !== "/dashboard" && path?.startsWith(`${href}/`));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm ${active ? "bg-background font-semibold text-accent" : "text-muted"}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <nav
          aria-label="Account and system"
          className="flex flex-wrap gap-4 border-l border-line pl-5 text-xs"
        >
          {secondaryLinks.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={path === href ? "page" : undefined}
              className={
                path === href ? "font-semibold text-accent" : "text-muted"
              }
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
