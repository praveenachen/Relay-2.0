import Link from "next/link";

export function CompletionActions({
  workflow,
  destinations,
}: {
  workflow: "learn" | "plan" | "collaborate";
  destinations: (string | null | undefined)[];
}) {
  const urls = [
    ...new Set(
      destinations.filter((value): value is string => {
        if (!value) return false;
        try {
          const url = new URL(value);
          return url.protocol === "https:" && Boolean(url.hostname);
        } catch {
          return false;
        }
      }),
    ),
  ];
  return (
    <div className="mt-5 flex flex-wrap items-start gap-3">
      {urls.length === 1 && (
        <a className="button" href={urls[0]} target="_blank" rel="noreferrer">
          View Completed Actions
        </a>
      )}
      {urls.length > 1 && (
        <details className="completion-destinations">
          <summary className="button">View Completed Actions</summary>
          <ul className="mt-3 space-y-2">
            {urls.map((url, index) => (
              <li key={url}>
                <a
                  className="text-link"
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {new URL(url).hostname} ? Output {index + 1}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}
      <Link className="button secondary" href="/dashboard">
        Return to Dashboard
      </Link>
      <Link className="button secondary" href={`/workflows/${workflow}`}>
        Start Another
      </Link>
    </div>
  );
}
