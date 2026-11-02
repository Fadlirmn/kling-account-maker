/**
 * Auth: admin cadangan dari env (DASHBOARD_USER / DASHBOARD_PASSWORD) + user dari tabel backend,
 * session = cookie ber-tanda-tangan HMAC-SHA256 (AUTH_SECRET). Web Crypto → jalan
 * di middleware (edge) maupun route handler (node).
 */
export const SESSION_COOKIE = "kurma_session";
export const SESSION_TTL_S = 60 * 60 * 24 * 7; // 7 hari

const enc = new TextEncoder();

function b64url(bytes: ArrayBuffer | Uint8Array): string {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = "";
  for (const c of b) s += String.fromCharCode(c);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function unb64url(s: string): Uint8Array {
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function secret(): string {
  const s = process.env.AUTH_SECRET;
  if (!s || s.length < 16) throw new Error("AUTH_SECRET belum diisi (min 16 karakter) — lihat .env.example");
  return s;
}

async function hmacKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", enc.encode(secret()), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

export type Session = { u: string; exp: number };

export async function signSession(user: string): Promise<string> {
  const payload: Session = { u: user, exp: Math.floor(Date.now() / 1000) + SESSION_TTL_S };
  const body = b64url(enc.encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(), enc.encode(body));
  return `${body}.${b64url(sig)}`;
}

export async function verifySession(token: string | undefined): Promise<Session | null> {
  if (!token) return null;
  const [body, sig] = token.split(".");
  if (!body || !sig) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await hmacKey(), unb64url(sig), enc.encode(body));
    if (!ok) return null;
    const s = JSON.parse(new TextDecoder().decode(unb64url(body))) as Session;
    if (!s.u || typeof s.exp !== "number" || s.exp < Date.now() / 1000) return null;
    return s;
  } catch {
    return null;
  }
}

/** Bandingkan constant-time (hindari timing attack pada password). */
function safeEqual(a: string, b: string): boolean {
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

const BACKEND = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api`;

export function isEnvAdmin(user: string): boolean {
  const u = process.env.DASHBOARD_USER ?? "";
  return !!u && safeEqual(user, u);
}

/** Admin env dicek lokal; user lain diverifikasi backend (tabel users, scrypt). */
export async function checkCredentials(user: string, password: string): Promise<boolean> {
  const p = process.env.DASHBOARD_PASSWORD ?? "";
  if (isEnvAdmin(user)) return !!p && safeEqual(password, p);
  try {
    const res = await fetch(`${BACKEND}/auth/verify`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username: user, password }),
      cache: "no-store",
    });
    return res.ok && (await res.json()).ok === true;
  } catch {
    return false;
  }
}

export type UserRole = "admin" | "member";

/**
 * Role user untuk sesi ini, dicek LIVE ke backend tiap request (hak akses berubah tanpa login ulang).
 * null = user sudah dihapus / backend mati (admin env tetap "admin").
 */
export async function sessionUserRole(user: string): Promise<UserRole | null> {
  if (isEnvAdmin(user)) return "admin";
  try {
    const res = await fetch(`${BACKEND}/auth/user-exists?username=${encodeURIComponent(user)}`, { cache: "no-store" });
    if (!res.ok) return null;
    const j = (await res.json()) as { exists?: boolean; role?: string | null };
    if (j.exists !== true) return null;
    return j.role === "admin" ? "admin" : "member";
  } catch {
    return null;
  }
}

/** Cookie tetap valid 7 hari; user DB yang sudah dihapus harus ditolak. */
export async function sessionUserActive(user: string): Promise<boolean> {
  return (await sessionUserRole(user)) !== null;
}

/** Hak akses member: hanya distribusi akun (halaman Accounts + API accounts baca/tandai/export). */
export const MEMBER_HOME = "/accounts";
export function memberPageAllowed(pathname: string): boolean {
  return pathname === "/accounts" || pathname.startsWith("/accounts/");
}
export function memberApiAllowed(pathname: string): boolean {
  return pathname === "/api/backend/summary" || pathname.startsWith("/api/backend/accounts") || pathname === "/api/auth/logout";
}
export const ROLE_HEADER = "x-user-role";
export const USER_HEADER = "x-user-name";

/** URL absolut untuk redirect, hormati proxy (cloudflared: X-Forwarded-Proto/Host). */
export function absoluteUrl(req: { headers: Headers; nextUrl: URL }, pathAndQuery: string): string {
  const proto = req.headers.get("x-forwarded-proto") ?? req.nextUrl.protocol.replace(":", "");
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? req.nextUrl.host;
  return `${proto}://${host}${pathAndQuery}`;
}
