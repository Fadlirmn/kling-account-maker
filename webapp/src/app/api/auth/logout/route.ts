import { NextResponse, type NextRequest } from "next/server";
import { absoluteUrl, SESSION_COOKIE } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const res = NextResponse.redirect(absoluteUrl(req, "/login"), { status: 303 });
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
