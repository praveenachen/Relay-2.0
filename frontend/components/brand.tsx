import Link from "next/link";
export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="brand" aria-label="Relay home">
      <svg aria-hidden="true" viewBox="0 0 32 32">
        <path
          d="M3 23h9V9h17M3 9h9M20 23h9"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
        <circle cx="12" cy="9" r="3" fill="currentColor" />
        <circle cx="20" cy="23" r="3" fill="currentColor" />
      </svg>
      <span>
        relay<span className="brand-dot">.</span>
      </span>
    </Link>
  );
}
