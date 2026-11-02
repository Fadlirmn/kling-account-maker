import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "@/lib/auth";

const BASE = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api`;

export async function forward(path: string, init?: RequestInit): Promise<Response> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "content-type": "application/json" },
      cache: "no-store",
    });
    return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
  } catch {
    return Response.json({ detail: "Backend tidak dapat dihubungi" }, { status: 503 });
  }
}

export async function currentUser(): Promise<string | null> {
  const s = await verifySession((await cookies()).get(SESSION_COOKIE)?.value);
  return s?.u ?? null;
}

export const unauthorized = () => Response.json({ detail: "unauthorized" }, { status: 401 });
