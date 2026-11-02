"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, FlashMsg } from "@/components/Alert";
import { Button, Card, KV, Loading, PageBar, Pill, type Tone } from "@/components/ui";
import { Field, Select } from "@/components/form";
import { StopRunButton } from "@/components/StopRunButton";
import { apiGet, apiPost, EMAIL_PROVIDERS, fmtDateTime, type EmailProvider, type Run, type Settings, type Summary } from "@/lib/api";

type Check = { ok: boolean; error?: string } & Record<string, unknown>;
interface Diagnostics {
  checked_at: string;
  db: Check & { backend?: string };
  config: { ok: boolean; problems: string[]; sources: string[]; site: string; signup_url: string };
  browser: Check & { path?: string; version?: string };
  geoip: Check & { path?: string };
  display: { xvfb: boolean; display: string };
  proxies: { total: number; bad: number; croxy: boolean };
  domains: { total: number; banned: number };
  email: { provider: string; chain: string[] };
  flow: { implemented: boolean; module: string };
  creator_running: boolean;
  last_run: Run | null;
}
type MailTest = { ok: boolean; provider: string | null; email?: string; skipped?: string[]; tried_failed?: string[]; ms: number };

const num = (v: string, lo: number, hi: number) => Math.max(lo, Math.min(hi, Number(v) || lo));
const okPill = (ok: boolean, yes = "OK", no = "Gagal") => <Pill sm tone={ok ? "success" : "err"}>{ok ? yes : no}</Pill>;
const runTone = (s: Run["status"]): Tone => (s === "success" ? "success" : s === "failed" ? "err" : s === "running" ? "info" : "warn");

/** Settings ▸ Testing — alat uji di server: diagnostik, run manual, uji provider email. Khusus admin. */
export default function TestingPage() {
  const [diag, setDiag] = useState<Diagnostics | null | undefined>(undefined);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [count, setCount] = useState(1);
  const [workers, setWorkers] = useState(1);
  const [provider, setProvider] = useState<EmailProvider | "">("");
  const [busy, setBusy] = useState<"run" | "mail" | "diag" | null>(null);
  const [mail, setMail] = useState<MailTest | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const flash = (ok: boolean, text: string) => { setMsg({ ok, text }); setTimeout(() => setMsg(null), 5000); };

  const loadDiag = useCallback(async () => {
    setBusy("diag");
    const [d, s] = await Promise.all([apiGet<Diagnostics>("/test/diagnostics"), apiGet<Summary>("/summary")]);
    setDiag(d); setSummary(s);
    setBusy(null);
  }, []);

  useEffect(() => {
    loadDiag();
    apiGet<Settings>("/settings").then((s) => { if (s) { setWorkers(Math.min(s.workers, 8)); } });
  }, [loadDiag]);

  // saat run berjalan, pantau status tiap 5 detik
  const running = summary?.creator_running ?? diag?.creator_running ?? false;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => apiGet<Summary>("/summary").then(setSummary), 5000);
    return () => clearInterval(t);
  }, [running]);

  const startRun = async () => {
    setBusy("run");
    const body: Record<string, unknown> = { count, workers };
    if (provider) body.provider = provider;
    const r = await apiPost<{ started: boolean }>("/test/run", body);
    if (r.status === 202) flash(true, `Run manual ${count} akun dimulai — lihat Settings › Logs`);
    else if (r.status === 409) flash(false, "Creator sedang berjalan");
    else flash(false, r.error ?? "Gagal memulai run");
    setBusy(null);
    apiGet<Summary>("/summary").then(setSummary);
  };

  const testMail = async () => {
    setBusy("mail");
    setMail(null);
    const r = await apiPost<MailTest>("/test/mail", provider ? { provider } : {});
    setMail(r.data ?? { ok: false, provider, ms: 0, tried_failed: [] });
    if (!r.data) flash(false, r.error ?? "Gagal menguji provider");
    setBusy(null);
  };

  if (diag === undefined) return <Loading />;

  return (
    <div className="max-w-[760px] w-full mx-auto flex flex-col gap-4">
      <PageBar
        meta={diag ? `Diagnostik ${fmtDateTime(diag.checked_at)} WIB` : "Diagnostik tidak tersedia"}
        right={
          <>
            {running && <StopRunButton stopping={summary?.stop_requested} />}
            <Button variant="outlined" size="sm" icon="refresh" spin={busy === "diag"} disabled={busy === "diag"} onClick={loadDiag}>Cek ulang</Button>
          </>
        }
      />
      <FlashMsg msg={msg} />

      {diag === null ? (
        <Alert tone="err" title="Backend tidak dapat dihubungi">Diagnostik tidak bisa dimuat.</Alert>
      ) : (
        <Card title="Diagnostik server" desc="Semua harus hijau sebelum run di server">
          <div className="box !gap-0 !py-1">
            <KV k="Database" v={<span className="inline-flex items-center gap-2">{okPill(diag.db.ok)} <span className="caption text-text3">{diag.db.backend ?? diag.db.error}</span></span>} />
            <KV k="Konfigurasi" v={<span className="inline-flex items-center gap-2 flex-wrap">{okPill(diag.config.ok, "Lengkap", "Kurang")} <span className="caption text-text3">{diag.config.ok ? diag.config.sources.join(" + ") : diag.config.problems.join("; ")}</span></span>} />
            <KV k="Browser Camoufox" v={<span className="inline-flex items-center gap-2">{okPill(diag.browser.ok, "Terpasang", "Belum")} <span className="caption text-text3 font-mono">{diag.browser.version ?? diag.browser.error}</span></span>} />
            <KV k="GeoIP MMDB" v={<span className="inline-flex items-center gap-2">{okPill(diag.geoip.ok, "Valid", "Rusak/hilang")} <span className="caption text-text3">{diag.geoip.error ?? ""}</span></span>} />
            <KV k="Display" v={diag.display.xvfb ? <Pill sm tone="success">Xvfb {diag.display.display} (headful)</Pill> : <Pill sm tone="warn">tanpa DISPLAY → headless</Pill>} />
            <KV k="Proxy" v={diag.proxies.total || diag.proxies.croxy ? <span>{diag.proxies.total} list · {diag.proxies.bad} blacklist{diag.proxies.croxy ? " · Croxy rotating" : ""}</span> : <Pill sm tone="warn">tanpa proxy (IP server)</Pill>} />
            <KV k="Domain webhook" v={`${diag.domains.total} aktif · ${diag.domains.banned} banned`} />
            <KV k="Email provider" v={<span>{diag.email.provider} <span className="caption text-text3">→ fallback {diag.email.chain.filter((p) => p !== diag.email.provider).join(", ") || "—"}</span></span>} />
            <KV k="Flow site" v={<span className="inline-flex items-center gap-2">{diag.flow.implemented ? <Pill sm tone="success">siap</Pill> : <Pill sm tone="warn">stub</Pill>} <span className="caption text-text3 font-mono">{diag.flow.module}</span></span>} />
            <KV k="Run terakhir" v={diag.last_run ? <span className="inline-flex items-center gap-2"><Pill sm tone={runTone(diag.last_run.status)}>{diag.last_run.status}</Pill> <span className="caption text-text3">{fmtDateTime(diag.last_run.started_at)} · ok {diag.last_run.created_ok} / gagal {diag.last_run.failed}</span></span> : "—"} />
          </div>
        </Card>
      )}

      <Card title="Run manual" desc="Jalankan batch kecil sekarang untuk menguji pipeline; progres di Settings › Logs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-3.5">
          <Field label="Jumlah akun" hint="1–100">
            <input type="number" min={1} max={100} className="input" value={count} onChange={(e) => setCount(num(e.target.value, 1, 100))} />
          </Field>
          <Field label="Worker" hint="1–8 browser paralel">
            <input type="number" min={1} max={8} className="input" value={workers} onChange={(e) => setWorkers(num(e.target.value, 1, 8))} />
          </Field>
          <Field label="Provider email" hint="Kosong = ikut Settings">
            <Select value={provider} onChange={(e) => setProvider(e.target.value as EmailProvider | "")}>
              <option value="">(ikut settings)</option>
              {EMAIL_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </Field>
        </div>
        <div className="card-actions">
          {running && <span className="caption text-info mr-auto">Creator sedang berjalan…</span>}
          <Button variant="primary" icon={running ? "sync" : "play_arrow"} spin={busy === "run" || running} disabled={busy !== null || running} onClick={startRun}>
            {running ? "Berjalan…" : "Mulai run manual"}
          </Button>
        </div>
      </Card>

      <Card title="Uji provider email" desc="Buat satu mailbox sementara tanpa menunggu OTP — memastikan provider bisa dipakai dari server">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outlined" icon="mail" spin={busy === "mail"} disabled={busy !== null} onClick={testMail}>Buat mailbox uji</Button>
          <span className="caption text-text3">provider: {provider || "ikut settings"}</span>
        </div>
        {mail && (
          <div className="box !gap-0 !py-1 mt-4">
            <KV k="Hasil" v={okPill(mail.ok, "Berhasil", "Gagal")} />
            <KV k="Provider dipakai" v={mail.provider ?? "—"} />
            {mail.email && <KV k="Mailbox" v={<span className="font-mono text-[12.5px] break-all">{mail.email}</span>} />}
            {!!mail.skipped?.length && <KV k="Dilewati (gagal)" v={mail.skipped.join(", ")} />}
            {!!mail.tried_failed?.length && <KV k="Semua gagal" v={mail.tried_failed.join(", ")} />}
            <KV k="Waktu" v={`${mail.ms} ms`} />
          </div>
        )}
      </Card>
    </div>
  );
}
