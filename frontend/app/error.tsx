"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-xl p-10">
      <h1 className="text-2xl font-semibold">
        We could not load your workspace.
      </h1>
      <p className="my-5 text-muted">
        Check that Relay is available, then try again.
      </p>
      <button className="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
