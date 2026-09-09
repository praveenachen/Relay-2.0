import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { userSchema } from "@/lib/schemas";

export async function requireUser() {
  const cookie = (await cookies()).get("relay_session");
  if (!cookie) redirect("/login");
  const response = await fetch(
    `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/users/me`,
    {
      headers: { Cookie: `relay_session=${cookie.value}` },
      cache: "no-store",
    },
  );
  if (response.status === 401) redirect("/login");
  if (!response.ok)
    throw new Error("Relay is temporarily unavailable. Please try again.");
  return userSchema.parse(await response.json());
}
