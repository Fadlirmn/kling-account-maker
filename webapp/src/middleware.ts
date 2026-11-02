import { NextResponse, type NextRequest } from "next/server";
import { absoluteUrl, SESSION_COOKIE, sessionUserActive, verifySession } from "@/lib/auth";

const PUBLIC = ["/login", "/api/auth/login", "/api/auth/logout"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC.some((p) => pathname === p)) return NextResponse.next();

  const session = await verifySession(req.cookies.get(SESSION_COOKIE)?.value);
  if (session && (await sessionUserActive(session.u))) return NextResponse.next();

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const q = pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
  const res = NextResponse.redirect(absoluteUrl(req, `/login${q}`));
  res.cookies.delete(SESSION_COOKIE);
  return res;
}

export const config = {
  // semua route kecuali aset statis Next dan file (favicon, logo, dsb.)
  matcher: ["/((?!_next/|.*\\..*).*)"],
};
