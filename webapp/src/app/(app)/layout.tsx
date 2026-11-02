import { Shell } from "@/components/Shell";
import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "@/lib/auth";
import { apiGet, type Summary } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [session, summary] = await Promise.all([
    verifySession((await cookies()).get(SESSION_COOKIE)?.value),
    apiGet<Summary>("/summary"),
  ]);
  return (
    <Shell user={session?.u} summary={summary}>
      {children}
    </Shell>
  );
}
