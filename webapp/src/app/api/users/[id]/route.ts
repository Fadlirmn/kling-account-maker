import { currentUser, forward } from "@/lib/usersServer";

export const runtime = "nodejs";

type Ctx = { params: Promise<{ id: string }> };

async function userId(ctx: Ctx): Promise<number | null> {
  const { id } = await ctx.params;
  return /^\d+$/.test(id) ? Number(id) : null;
}

export async function PUT(req: Request, ctx: Ctx) {
  if (!(await currentUser())) return Response.json({ detail: "unauthorized" }, { status: 401 });
  const id = await userId(ctx);
  if (id === null) return Response.json({ detail: "User tidak ditemukan" }, { status: 404 });
  return forward(`/users/${id}/password`, { method: "PUT", body: await req.text() });
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const me = await currentUser();
  if (!me) return Response.json({ detail: "unauthorized" }, { status: 401 });
  const id = await userId(ctx);
  if (id === null) return Response.json({ detail: "User tidak ditemukan" }, { status: 404 });
  const list = await forward("/users");
  if (!list.ok) return list;
  const target = ((await list.json()) as Array<{ id: number; username: string }>).find((u) => u.id === id);
  if (!target) return Response.json({ detail: "User tidak ditemukan" }, { status: 404 });
  if (target.username === me) return Response.json({ detail: "Tidak bisa menghapus akun sendiri" }, { status: 409 });
  return forward(`/users/${id}`, { method: "DELETE" });
}
