"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BriefcaseBusiness,
  CalendarDays,
  ChevronLeft,
  CircleUserRound,
  FolderHeart,
  GraduationCap,
  House,
  Inbox,
  Menu,
  PlugZap,
  Settings,
  X,
} from "lucide-react";
import { usePendingApprovals, useUser } from "@/hooks/queries";
import { auth } from "@/features/auth/api";

const primaryLinks = [
  ["/dashboard", "Home", House],
  ["/my-day", "My Day", CalendarDays],
  ["/inbox", "Inbox", Inbox],
] as const;
const spaceLinks = [
  ["/spaces/school", "School", GraduationCap, "school"],
  ["/spaces/work", "Work", BriefcaseBusiness, "work"],
  ["/spaces/personal", "Personal", FolderHeart, "personal"],
] as const;
const secondaryLinks = [
  ["/runs", "Activity", Activity],
  ["/connections", "Connections", PlugZap],
  ["/settings", "Settings", Settings],
] as const;

export function WorkspaceNav({ name }: { name: string }) {
  const path = usePathname();
  const user = useUser();
  const pendingApprovals = usePendingApprovals();
  const router = useRouter();
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const logout = useMutation({
    mutationFn: auth.logout,
    onSuccess: () => {
      cache.clear();
      router.replace("/login");
      router.refresh();
    },
  });
  const active = (href: string) =>
    path === href || (href !== "/dashboard" && path?.startsWith(`${href}/`));

  return (
    <>
      <button
        className="mobile-nav-trigger"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
      >
        <Menu />
      </button>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`workspace-sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-brand-row">
          <Link
            href="/dashboard"
            className="workspace-logo"
            onClick={() => setOpen(false)}
          >
            <span className="workspace-logo-mark">R</span>
            <span>Relay</span>
          </Link>
          <button
            className="sidebar-close"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X />
          </button>
        </div>
        <nav aria-label="Workspace" className="sidebar-nav">
          <div className="sidebar-group">
            {primaryLinks.map(([href, label, Icon]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={active(href) ? "page" : undefined}
                className={`sidebar-link ${active(href) ? "active" : ""}`}
              >
                <Icon />
                <span>{label}</span>
                {href === "/inbox" &&
                  (pendingApprovals.data?.length || 0) > 0 && (
                    <span className="sidebar-count">
                      {pendingApprovals.data?.length}
                    </span>
                  )}
              </Link>
            ))}
          </div>
          <div className="sidebar-group">
            <p className="sidebar-label">Spaces</p>
            {spaceLinks.map(([href, label, Icon, tone]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={active(href) ? "page" : undefined}
                className={`sidebar-link space-link ${tone} ${active(href) ? "active" : ""}`}
              >
                <span className="space-icon">
                  <Icon />
                </span>
                <span>{label}</span>
              </Link>
            ))}
          </div>
          <div className="sidebar-group sidebar-secondary">
            {secondaryLinks.map(([href, label, Icon]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={active(href) ? "page" : undefined}
                className={`sidebar-link ${active(href) ? "active" : ""}`}
              >
                <Icon />
                <span>{label}</span>
              </Link>
            ))}
          </div>
        </nav>
        <details className="sidebar-account">
          <summary>
            <CircleUserRound />
            <span>
              <strong>{user.data?.name || name}</strong>
              <small>Personal workspace</small>
            </span>
            <ChevronLeft />
          </summary>
          <div>
            <button disabled={logout.isPending} onClick={() => logout.mutate()}>
              Sign out
            </button>
          </div>
        </details>
      </aside>
    </>
  );
}
