"use client";

import { useEffect, useState } from "react";
import { Button, Card, Loading, PageBar, Pill } from "@/components/ui";
import { Field, Select, Switch } from "@/components/form";
import { Alert, FlashMsg } from "@/components/Alert";
import { Icon } from "@/components/Icon";
import { apiGet, apiPut, EMAIL_PROVIDERS, fmtDateTime, type EmailProvider, type Settings, type Summary } from "@/lib/api";

type Draft = Omit<Settings, "config_version">;

const toDraft = (s: Settings): Draft => ({
  workers: s.workers, batch_size: s.batch_size, email_provider: s.email_provider, max_daily_success: s.max_daily_success,
  standby_target: s.standby_target, refill_interval_minutes: s.refill_interval_minutes, enable_scheduler: s.enable_scheduler,
  schedule_time: s.schedule_time, schedule_jitter_minutes: s.schedule_jitter_minutes, max_attempts_per_slot: s.max_attempts_per_slot,
  delay_between_accounts: s.delay_between_accounts, browser_concurrency: s.browser_concurrency,
  debug_screenshots: s.debug_screenshots, retention_days: s.retention_days,
});

const num = (v: string, lo: number, hi: number) => Math.max(lo, Math.min(hi, Number(v) || 0));

/** Settings ▸ Umum — tiga blok: Pool akun · Otomatis · Lanjutan (disembunyikan). */
export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null | undefined>(undefined);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [advanced, setAdvanced] = useState(false);
  // interval isi ulang terakhir yang > 0, supaya switch "isi ulang" bisa dimatikan/dinyalakan tanpa kehilangan angkanya
  const [lastRefill, setLastRefill] = useState(60);

  useEffect(() => {
    apiGet<Settings>("/settings").then((s) => {
      setSettings(s);
      if (s) { setDraft(toDraft(s)); if (s.refill_interval_minutes > 0) setLastRefill(s.refill_interval_minutes); }
    });
    apiGet<Summary>("/summary").then(setSummary);
  }, []);

  const dirty = settings && draft && JSON.stringify(toDraft(settings)) !== JSON.stringify(draft);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    const r = await apiPut<Settings>("/settings", draft);
    if (r.data) { setSettings(r.data); setDraft(toDraft(r.data)); setMsg({ ok: true, text: `Tersimpan · config v${r.data.config_version}` }); }
    else setMsg({ ok: false, text: r.error ?? "Gagal menyimpan" });
    setSaving(false);
    setTimeout(() => setMsg(null), 5000);
  };

  if (settings === undefined) return <Loading />;
  if (!settings || !draft) return <Alert tone="err" title="Backend tidak dapat dihubungi">Pengaturan tidak bisa dimuat.</Alert>;

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });
  const refillOn = draft.refill_interval_minutes > 0;
  const toggleRefill = (on: boolean) => {
    if (on) set("refill_interval_minutes", lastRefill || 60);
    else { setLastRefill(draft.refill_interval_minutes || lastRefill); set("refill_interval_minutes", 0); }
  };
  const standby = summary?.standby ?? null;

  return (
    <div className="max-w-[640px] w-full mx-auto flex flex-col gap-4">
      <PageBar
        meta={`Config v${settings.config_version}`}
        right={summary ? <Pill tone={summary.flow_implemented ? "success" : "warn"} dot>{summary.flow_implemented ? "Flow siap" : "Flow masih stub"}</Pill> : undefined}
      />
      <FlashMsg msg={msg} />

      {/* ── 1. Pool akun: dua angka yang paling sering diubah ─────────────── */}
      <Card title="Pool akun" desc="Berapa akun standby yang harus selalu tersedia">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
          <Field label="Target akun standby" hint={standby !== null ? `Sekarang ${standby} standby` : "0 = tidak dijaga"}>
            <input type="number" min={0} max={100000} className="input" value={draft.standby_target}
              onChange={(e) => set("standby_target", num(e.target.value, 0, 100000))} />
          </Field>
          <Field label="Batas sukses per hari" hint="Akun baru maksimal per 24 jam">
            <input type="number" min={1} max={100000} className="input" value={draft.max_daily_success}
              onChange={(e) => set("max_daily_success", num(e.target.value, 1, 100000))} />
          </Field>
        </div>
      </Card>

      {/* ── 2. Otomatis: dua saklar, detail muncul hanya saat nyala ──────────── */}
      <Card title="Otomatis" desc="Kapan creator jalan sendiri">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3">
            <Switch label="Batch harian" desc="Buat akun setiap hari pada jam tertentu" checked={draft.enable_scheduler} onChange={(e) => set("enable_scheduler", e.target.checked)} />
            {draft.enable_scheduler && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3.5 pl-0 sm:pl-[52px]">
                <Field label="Jam (WIB)">
                  <input type="time" className="input" value={draft.schedule_time} onChange={(e) => set("schedule_time", e.target.value)} />
                </Field>
                <Field label="Akun per batch">
                  <input type="number" min={1} max={500} className="input" value={draft.batch_size}
                    onChange={(e) => set("batch_size", num(e.target.value, 1, 500))} />
                </Field>
              </div>
            )}
          </div>
          <div className="border-t border-line-soft" />
          <div className="flex flex-col gap-3">
            <Switch label="Isi ulang otomatis" desc="Tambah akun saat standby di bawah target" checked={refillOn} onChange={(e) => toggleRefill(e.target.checked)} />
            {refillOn && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3.5 pl-0 sm:pl-[52px]">
                <Field label="Cek setiap (menit)">
                  <input type="number" min={1} max={1440} className="input" value={draft.refill_interval_minutes}
                    onChange={(e) => set("refill_interval_minutes", num(e.target.value, 1, 1440))} />
                </Field>
              </div>
            )}
          </div>
          {summary && (
            <p className="caption text-text3">
              Berikutnya: batch {summary.scheduler.next_run_at ? `${fmtDateTime(summary.scheduler.next_run_at)} WIB` : "—"} · isi ulang {summary.scheduler.next_refill_at ? `${fmtDateTime(summary.scheduler.next_refill_at)} WIB` : "—"}
            </p>
          )}
        </div>
      </Card>

      {/* ── 3. Lanjutan: disembunyikan, jarang diubah ───────────────────────── */}
      <button
        type="button"
        className="flex items-center gap-2 self-start caption text-text2 hover:text-text"
        onClick={() => setAdvanced(!advanced)}
        aria-expanded={advanced}
      >
        <Icon name={advanced ? "expand_less" : "expand_more"} size="sm" />
        {advanced ? "Sembunyikan pengaturan lanjutan" : "Pengaturan lanjutan (browser, email, retry)"}
      </button>

      {advanced && (
        <Card title="Lanjutan" desc="Biarkan default kecuali tahu dampaknya">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
            <Field label="Provider email" hint="Fallback otomatis ke provider lain">
              <Select value={draft.email_provider} onChange={(e) => set("email_provider", e.target.value as EmailProvider)}>
                {EMAIL_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
              </Select>
            </Field>
            <Field label="Browser paralel" hint="Worker per batch (dibatasi RAM)">
              <input type="number" min={1} max={16} className="input" value={draft.workers}
                onChange={(e) => { const w = num(e.target.value, 1, 16); setDraft({ ...draft, workers: w, browser_concurrency: Math.min(draft.browser_concurrency, Math.max(1, w)) }); }} />
            </Field>
            <Field label="Percobaan per akun" hint="Ulang kalau gagal">
              <input type="number" min={1} max={20} className="input" value={draft.max_attempts_per_slot}
                onChange={(e) => set("max_attempts_per_slot", num(e.target.value, 1, 20))} />
            </Field>
            <Field label="Jeda antar akun (detik)" hint="Beri waktu proxy ganti IP">
              <input type="number" min={0} max={600} className="input" value={draft.delay_between_accounts}
                onChange={(e) => set("delay_between_accounts", num(e.target.value, 0, 600))} />
            </Field>
            <Field label="Geser jam batch (menit)" hint="Acak 0..n agar tidak seragam">
              <input type="number" min={0} max={120} className="input" value={draft.schedule_jitter_minutes}
                onChange={(e) => set("schedule_jitter_minutes", num(e.target.value, 0, 120))} />
            </Field>
            <Field label="Simpan riwayat run (hari)" hint="0 = selamanya">
              <input type="number" min={0} max={3650} className="input" value={draft.retention_days}
                onChange={(e) => set("retention_days", num(e.target.value, 0, 3650))} />
            </Field>
            <Field label="Browser bersamaan maks" hint="Semaphore Firefox (≤ worker)">
              <input type="number" min={1} max={8} className="input" value={draft.browser_concurrency}
                onChange={(e) => set("browser_concurrency", num(e.target.value, 1, 8))} />
            </Field>
          </div>
          <div className="mt-4">
            <Switch label="Screenshot debug" desc="Simpan screenshot tiap langkah (boros disk)" checked={draft.debug_screenshots} onChange={(e) => set("debug_screenshots", e.target.checked)} />
          </div>
          {summary && (
            <p className="caption text-text3 mt-4">
              Proxy {summary.proxies.total} ({summary.proxies.bad} blacklist{summary.proxies.croxy ? ", Croxy" : ""}) · domain {summary.domains.total} ({summary.domains.banned} banned) · kredensial & proxy hanya dari <span className="font-mono">.env</span>.
            </p>
          )}
        </Card>
      )}

      {dirty && (
        <div className="card-actions !mt-0 sticky bottom-3 z-10 bg-paper border border-divider rounded-[10px] px-3 py-2 shadow-card">
          <span className="caption t-warn mr-auto">Perubahan belum disimpan</span>
          <Button variant="outlined" size="sm" onClick={() => setDraft(toDraft(settings))}>Batal</Button>
          <Button variant="primary" size="sm" icon="save" spin={saving} disabled={saving} onClick={save}>
            {saving ? "Menyimpan…" : "Simpan"}
          </Button>
        </div>
      )}
    </div>
  );
}
