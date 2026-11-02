import { NextResponse, type NextRequest } from "next/server";
import {
  absoluteUrl, MEMBER_HOME, memberApiAllowed, memberPageAllowed, ROLE_HEADER, SESSION_COOKIE,
  sessionUserRole, USER_HEADER, verifySession,
} from "@/lib/auth";

const PUBLIC = ["/login", "/api/auth/login", "/api/auth/logout"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC.some((p) => pathname === p)) return NextResponse.next();

  const session = await verifySession(req.cookies.get(SESSION_COOKIE)?.value);
  const role = session ? await sessionUserRole(session.u) : null;

  if (session && role) {
    // member: hanya distribusi akun
    if (role === "member") {
      if (pathname.startsWith("/api/")) {
        if (!memberApiAllowed(pathname)) return NextResponse.json({ detail: "forbidden: khusus admin" }, { status: 403 });
      } else if (!memberPageAllowed(pathname)) {
        return NextResponse.redirect(absoluteUrl(req, MEMBER_HOME));
      }
    }
    const headers = new Headers(req.headers);
    headers.set(ROLE_HEADER, role);
    headers.set(USER_HEADER, session.u);
    return NextResponse.next({ request: { headers } });
  }

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
