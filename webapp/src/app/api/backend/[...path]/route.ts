import { NextRequest } from "next/server";
import { ROLE_HEADER } from "@/lib/auth";

// Proxy server-side ke backend FastAPI. Middleware sudah memproteksi /api/* (401 tanpa session),
// jadi tidak ada cek auth di sini. Body diteruskan apa adanya (JSON, CSV download, dsb).

const BASE = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api`;

// endpoint sensitif hanya lewat route handler khusus (/api/users) atau server-side
const BLOCKED = new Set(["auth", "users"]);

// aksi massal yang boleh dilakukan member (distribusi akun): tandai dipakai / belum dipakai
const MEMBER_BULK_ACTIONS = new Set(["mark_used", "mark_unused"]);

/** Member: GET summary/accounts*, POST accounts/bulk hanya mark_used|mark_unused. Lainnya 403. */
function memberAllowed(path: string[], method: string, body: string): boolean {
  const p = path.join("/");
  if (method === "GET") return p === "summary" || p.startsWith("accounts");
  if (method === "POST" && p === "accounts/bulk") {
    try {
      return MEMBER_BULK_ACTIONS.has(JSON.parse(body)?.action);
    } catch {
      return false;
    }
  }
  return false;
}

async function proxy(req: NextRequest, path: string[], method: string) {
  if (BLOCKED.has(path[0] ?? "")) return Response.json({ detail: "forbidden" }, { status: 403 });
  const body = method === "GET" ? undefined : await req.text();
  const role = req.headers.get(ROLE_HEADER);
  if (role === "member" && !memberAllowed(path, method, body ?? "")) {
    return Response.json({ detail: "forbidden: khusus admin" }, { status: 403 });
  }
  const url = `${BASE}/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  try {
    const res = await fetch(url, {
      method,
      headers,
      body,
      cache: "no-store",
    });
    const out = new Headers();
    for (const h of ["content-type", "content-disposition"]) {
      const v = res.headers.get(h);
      if (v) out.set(h, v);
    }
    return new Response(res.body, { status: res.status, headers: out });
  } catch (e) {
    console.error(`Backend proxy ${method} ${url}:`, e);
    return Response.json({ detail: "Backend tidak dapat dihubungi" }, { status: 503 });
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, { params }: Ctx) {
  return proxy(req, (await params).path ?? [], "GET");
}
export async function POST(req: NextRequest, { params }: Ctx) {
  return proxy(req, (await params).path ?? [], "POST");
}
export async function PUT(req: NextRequest, { params }: Ctx) {
  return proxy(req, (await params).path ?? [], "PUT");
}
