import Link from "next/link";
import { ApiError } from "@/lib/api";

export function PageTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="mb-9">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
        {title}
      </h1>
      <p className="mt-3 max-w-2xl leading-7 text-muted">{description}</p>
    </header>
  );
}
export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div role="alert" className="notice error">
      {error instanceof Error ? error.message : "Something went wrong."}
      {error instanceof ApiError && error.status === 401 && (
        <Link className="ml-2 underline" href="/login">
          Sign in
        </Link>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <p role="status" className="py-10 text-muted">
      Loading your workspace...
    </p>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line p-8">
      <h3 className="font-medium">{title}</h3>
      <div className="mt-2 text-sm leading-6 text-muted">{children}</div>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className="badge">{value.toLowerCase().replaceAll("_", " ")}</span>
  );
}
