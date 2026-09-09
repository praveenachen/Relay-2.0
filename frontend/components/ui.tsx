import Link from "next/link";
import {
  Activity,
  AlertCircle,
  Check,
  CircleSlash,
  Clock3,
  CornerDownRight,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { statusFor } from "@/features/workflows/status";

export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action && <div className="page-action">{action}</div>}
    </header>
  );
}
export function ErrorMessage({
  error,
  retry,
  title = "Something needs attention",
}: {
  error: unknown;
  retry?: () => void;
  title?: string;
}) {
  if (!error) return null;
  return (
    <div role="alert" className="notice error">
      <AlertCircle aria-hidden="true" />
      <div>
        <p className="font-medium">{title}</p>
        <p>
          {error instanceof Error
            ? error.message
            : "We could not complete this request."}
        </p>
        <div className="mt-3 flex gap-4">
          {error instanceof ApiError && error.status === 401 ? (
            <Link className="text-link" href="/login">
              Sign in again
            </Link>
          ) : (
            retry && (
              <button className="text-link" onClick={retry}>
                Try again
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
export function Loading({
  label = "Loading your workspace",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      <div className="skeleton skeleton-heading" />
      <div className="skeleton skeleton-subtitle" />
      <div className="skeleton skeleton-row" />
      <div className="skeleton skeleton-row" />
    </div>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <CornerDownRight aria-hidden="true" />
      <div>
        <h3>{title}</h3>
        <div className="empty-copy">{children}</div>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  );
}
const statusIcons = {
  clock: Clock3,
  activity: Activity,
  check: Check,
  warning: AlertCircle,
  stop: CircleSlash,
};
export function Status({ value }: { value: string }) {
  const presentation = statusFor(value),
    Icon = statusIcons[presentation.symbol];
  return (
    <span className={`status-badge ${presentation.tone}`}>
      <Icon aria-hidden="true" />
      {presentation.label}
    </span>
  );
}
