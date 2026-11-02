import { isEnvAdmin } from "@/lib/auth";
import { currentUser, forward, unauthorized } from "@/lib/usersServer";

export const runtime = "nodejs";

export async function GET() {
  const me = await currentUser();
  if (!me) return unauthorized();
  const res = await forward("/users");
  if (!res.ok) return res;
  return Response.json({
    me,
    env_admin: process.env.DASHBOARD_USER || null,
    me_is_env_admin: isEnvAdmin(me),
    users: await res.json(),
  });
}

export async function POST(req: Request) {
  if (!(await currentUser())) return unauthorized();
  return forward("/users", { method: "POST", body: await req.text() });
}
