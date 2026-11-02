import { NextResponse, type NextRequest } from "next/server";
import { absoluteUrl, checkCredentials, SESSION_COOKIE, SESSION_TTL_S, signSession } from "@/lib/auth";

export const runtime = "nodejs";

function safeNext(v: FormDataEntryValue | null): string {
  const s = typeof v === "string" ? v : "";
  return s.startsWith("/") && !s.startsWith("//") ? s : "/";
}

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const user = String(form.get("user") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const next = safeNext(form.get("next"));

  if (!(await checkCredentials(user, password))) {
    await new Promise((r) => setTimeout(r, 600)); // rem brute-force sederhana
    const q = `?error=1${next !== "/" ? `&next=${encodeURIComponent(next)}` : ""}`;
    return NextResponse.redirect(absoluteUrl(req, `/login${q}`), { status: 303 });
  }

  const token = await signSession(user);
  const res = NextResponse.redirect(absoluteUrl(req, next), { status: 303 });
  const https = absoluteUrl(req, "/").startsWith("https:");
  res.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: https,
    path: "/",
    maxAge: SESSION_TTL_S,
  });
  return res;
}
