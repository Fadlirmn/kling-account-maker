import { NextRequest } from "next/server";

// Proxy server-side ke backend FastAPI. Middleware sudah memproteksi /api/* (401 tanpa session),
// jadi tidak ada cek auth di sini. Body diteruskan apa adanya (JSON, CSV download, dsb).

const BASE = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api`;

// endpoint sensitif hanya lewat route handler khusus (/api/users) atau server-side
const BLOCKED = new Set(["auth", "users"]);

async function proxy(req: NextRequest, path: string[], method: string) {
  if (BLOCKED.has(path[0] ?? "")) return Response.json({ detail: "forbidden" }, { status: 403 });
  const url = `${BASE}/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  try {
    const res = await fetch(url, {
      method,
      headers,
      body: method === "GET" ? undefined : await req.text(),
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
