// Klien API backend + tipe TypeScript (sesuai JSON backend/api.py).
//
// Server component: fetch langsung ke API_BASE_URL (di compose: http://backend:8000).
// Client component ("use client"): lewat proxy Next /api/backend/* (dilindungi middleware).

function base(): string {
  if (typeof window !== "undefined") return "/api/backend";
  return `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api`;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T | null> {
  try {
    const res = await fetch(`${base()}${path}`, { cache: "no-store", signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch (e) {
    if ((e as { name?: string })?.name === "AbortError") return null;
    console.error(`API GET ${path}:`, e);
    return null;
  }
}

async function send<T>(method: "POST" | "PUT", path: string, body?: unknown) {
  try {
    const res = await fetch(`${base()}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    let data: T | null = null;
    let error: string | null = null;
    try {
      const j = await res.json();
      if (res.ok) data = j as T;
      else error = typeof j?.detail === "string" ? j.detail : JSON.stringify(j?.detail ?? j);
    } catch {
      /* body kosong */
    }
    return { data, status: res.status, error };
  } catch (e) {
    console.error(`API ${method} ${path}:`, e);
    return { data: null, status: 0, error: "Backend tidak dapat dihubungi" };
  }
}

export const apiPost = <T,>(path: string, body?: unknown) => send<T>("POST", path, body);
export const apiPut = <T,>(path: string, body: unknown) => send<T>("PUT", path, body);

// ---------- Types ----------

export type RunStatus = "running" | "success" | "partial" | "failed";
export type RunTrigger = "manual" | "scheduled" | "auto_refill";

export interface Run {
  id: number;
  trigger: RunTrigger;
  config_version: number;
  requested: number;
  workers: number;
  provider: string | null;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  created_ok: number;
  failed: number;
  skipped: number;
  error_message: string | null;
  log?: string | null;          // hanya GET /runs/{id}
  accounts?: AccountLite[];     // hanya GET /runs/{id}
}

export interface RunLog {
  run_id: number;
  status: RunStatus;
  source: "file" | "db";
  truncated: boolean;
  log: string;
}

export type AccountStatus = "pending" | "standby" | "active" | "exhausted" | "used" | "banned" | "failed";
export const ACCOUNT_STATUSES: AccountStatus[] = ["pending", "standby", "active", "exhausted", "used", "banned", "failed"];

export interface AccountLite {
  id: number;
  email: string;
  password: string;          // satu password untuk semua akun (KLING_DEFAULT_PASSWORD) — ditampilkan di tabel
  status: AccountStatus;
  user_id: string;
  email_mode: string;
  attempts: number;
  credits: string;
  plan: string;
  error: string | null;
  run_id: number | null;
  created_at: string;
  updated_at: string;
  has_cookies?: boolean;
}

export interface Account extends AccountLite {
  otp: string;
  proxy: string;
  cookies: string;
  has_cookies: boolean;
}

export interface AccountsPage {
  items: AccountLite[];
  total: number;
  page: number;
  size: number;
  counts: Record<AccountStatus, number>;
}

export interface TrendPoint {
  day: string;      // YYYY-MM-DD (WIB)
  created: number;
  failed: number;
}

export interface Summary {
  last_run: Run | null;
  standby: number;
  active: number;
  total: number;
  created_24h: number;
  failed_24h: number;
  created_today: number;
  counts: Record<AccountStatus, number>;
  creator_running: boolean;
  stop_requested: boolean;
  flow_implemented: boolean;
  standby_target: number;
  proxies: { total: number; bad: number; croxy: boolean };
  domains: { total: number; banned: number };
  scheduler: { enabled: boolean; schedule_time: string | null; next_run_at: string | null; next_refill_at: string | null };
}

export type EmailProvider = "webhook" | "local_tempmail" | "1secmail" | "mailtm" | "gptmail";
export const EMAIL_PROVIDERS: EmailProvider[] = ["webhook", "local_tempmail", "1secmail", "mailtm", "gptmail"];

export interface Settings {
  workers: number;
  batch_size: number;
  email_provider: EmailProvider;
  max_daily_success: number;
  standby_target: number;
  refill_interval_minutes: number;
  enable_scheduler: boolean;
  schedule_time: string;
  schedule_jitter_minutes: number;
  max_attempts_per_slot: number;
  delay_between_accounts: number;
  browser_concurrency: number;
  debug_screenshots: boolean;
  retention_days: number;
  config_version: number;
}

export type UserRole = "admin" | "member";
export interface DashboardUser {
  id: number;
  username: string;
  role: UserRole;
  created_at: string;
  updated_at: string;
}

export interface UsersResponse {
  me: string;
  env_admin: string | null;
  me_is_env_admin: boolean;
  users: DashboardUser[];
}

// ---------- Format helper tanggal ----------

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("id-ID", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta",
  });
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Jakarta" });
}

export function durationMin(run: Pick<Run, "started_at" | "finished_at">): number | null {
  if (!run.finished_at) return null;
  return Math.max(0, Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 60000));
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "baru saja";
  if (m < 60) return `${m} menit lalu`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} jam lalu`;
  return `${Math.round(h / 24)} hari lalu`;
}

export const TRIGGER_LABEL: Record<RunTrigger, string> = {
  manual: "manual", scheduled: "jadwal", auto_refill: "isi ulang otomatis",
};
