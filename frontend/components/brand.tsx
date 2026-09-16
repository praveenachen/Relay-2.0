import Link from "next/link";
export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="brand" aria-label="Relay home">
      <span className="brand-mark" aria-hidden="true">
        R
      </span>
      <span>Relay</span>
    </Link>
  );
}
