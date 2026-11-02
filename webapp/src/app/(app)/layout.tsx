import { Shell } from "@/components/Shell";
import { cookies, headers } from "next/headers";
import { ROLE_HEADER, SESSION_COOKIE, verifySession, type UserRole } from "@/lib/auth";
import { apiGet, type Summary } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [session, summary, hdrs] = await Promise.all([
    verifySession((await cookies()).get(SESSION_COOKIE)?.value),
    apiGet<Summary>("/summary"),
    headers(),
  ]);
  const role: UserRole = hdrs.get(ROLE_HEADER) === "admin" ? "admin" : "member";
  return (
    <Shell user={session?.u} role={role} summary={summary}>
      {children}
    </Shell>
  );
}
