"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePendingApprovals, useUser } from "@/hooks/queries";
import { auth } from "@/features/auth/api";
import { ErrorMessage } from "@/components/ui";

const primaryLinks = [
  ["/dashboard", "Home"],
  ["/workflows/learn", "Notes"],
  ["/workflows/plan", "Planner"],
  ["/workflows/collaborate", "Projects"],
  ["/approvals", "Review"],
] as const;

const secondaryLinks = [
  ["/runs", "Activity"],
  ["/connections", "Connections"],
  ["/settings", "Settings"],
] as const;

export function WorkspaceNav({ name }: { name: string }) {
  const path = usePathname();
  const user = useUser();
  const pendingApprovals = usePendingApprovals();
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
    <header className="workspace-topbar">
      <div className="workspace-nav-inner">
        <Link href="/dashboard" className="workspace-logo">
          <span className="workspace-logo-mark">↗</span> relay
        </Link>
        <nav aria-label="Workspace" className="primary-nav">
          {primaryLinks.map(([href, label]) => {
            const active =
              path === href ||
              (href !== "/dashboard" && path?.startsWith(`${href}/`));
            const reviewCount = pendingApprovals.data?.length || 0;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`nav-pill ${active ? "active" : ""}`}
              >
                {label}
                {href === "/approvals" && reviewCount > 0 && (
                  <span
                    className="nav-count"
                    aria-label={`${reviewCount} items`}
                  >
                    {reviewCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <details className="account-menu">
          <summary>{user.data?.name || name}</summary>
          <nav aria-label="Account and settings">
            {secondaryLinks.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={path === href ? "page" : undefined}
              >
                {label}
              </Link>
            ))}
            <button disabled={logout.isPending} onClick={() => logout.mutate()}>
              Sign out
            </button>
          </nav>
        </details>
        <ErrorMessage error={logout.error} />
      </div>
    </header>
  );
}
