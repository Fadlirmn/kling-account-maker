"use client";

import { useEffect, useState } from "react";
import { Button, Card, KV, Loading, PageBar, Pill } from "@/components/ui";
import { Field, Fieldset, Select, Switch } from "@/components/form";
import { Alert, FlashMsg } from "@/components/Alert";
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
const input = "input";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null | undefined>(undefined);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    apiGet<Settings>("/settings").then((s) => { setSettings(s); if (s) setDraft(toDraft(s)); });
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

  return (
    <div className="max-w-[760px] w-full mx-auto flex flex-col gap-4">
      <PageBar meta={`Config v${settings.config_version} · perubahan parameter pembuatan akun menaikkan CONFIG_VERSION`} />
      <FlashMsg msg={msg} />

      <Card title="Jadwal & Isi Ulang" desc="Waktu WIB · batch harian dan penjagaan pool standby">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
          <Field label="Jam batch harian (WIB)">
            <input type="time" className={input} value={draft.schedule_time} onChange={(e) => set("schedule_time", e.target.value)} />
          </Field>
          <Field label="Geser jam (menit)" hint="Jadwal diacak 0..n menit tiap hari (0 = persis)">
            <input type="number" min={0} max={120} className={input} value={draft.schedule_jitter_minutes}
              onChange={(e) => set("schedule_jitter_minutes", num(e.target.value, 0, 120))} />
          </Field>
          <Field label="Ukuran batch" hint="Slot per run terjadwal / isi ulang (1–500)">
            <input type="number" min={1} max={500} className={input} value={draft.batch_size}
              onChange={(e) => set("batch_size", num(e.target.value, 1, 500))} />
          </Field>
          <Field label="Target pool standby" hint="Isi ulang otomatis sampai jumlah ini (0 = mati)">
            <input type="number" min={0} max={100000} className={input} value={draft.standby_target}
              onChange={(e) => set("standby_target", num(e.target.value, 0, 100000))} />
          </Field>
          <Field label="Interval isi ulang (menit)" hint="Cek pool tiap n menit (0 = mati)">
            <input type="number" min={0} max={1440} className={input} value={draft.refill_interval_minutes}
              onChange={(e) => set("refill_interval_minutes", num(e.target.value, 0, 1440))} />
          </Field>
          <Field label="Batas sukses harian" hint="Akun standby/active maks per 24 jam">
            <input type="number" min={1} max={100000} className={input} value={draft.max_daily_success}
              onChange={(e) => set("max_daily_success", num(e.target.value, 1, 100000))} />
          </Field>
        </div>
        <Fieldset legend="Scheduler" className="mt-4">
          <Switch label="Batch harian aktif" desc="Run otomatis tiap hari pada jam di atas" checked={draft.enable_scheduler} onChange={(e) => set("enable_scheduler", e.target.checked)} />
        </Fieldset>
      </Card>

      <Card title="Pembuatan Akun" desc="Parameter engine: browser, provider email, retry">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
          <Field label="Worker" hint="Browser paralel per run (1–16; dibatasi RAM guard)">
            <input type="number" min={1} max={16} className={input} value={draft.workers}
              onChange={(e) => set("workers", num(e.target.value, 1, 16))} />
          </Field>
          <Field label="Browser bersamaan maks" hint="Semaphore Firefox (1–8); cegah heap corruption di VPS">
            <input type="number" min={1} max={8} className={input} value={draft.browser_concurrency}
              onChange={(e) => set("browser_concurrency", num(e.target.value, 1, 8))} />
          </Field>
          <Field label="Provider email" hint="Fallback otomatis ke provider lain jika gagal">
            <Select value={draft.email_provider} onChange={(e) => set("email_provider", e.target.value as EmailProvider)}>
              {EMAIL_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </Field>
          <Field label="Attempt per slot" hint="Percobaan ulang per akun (1–20)">
            <input type="number" min={1} max={20} className={input} value={draft.max_attempts_per_slot}
              onChange={(e) => set("max_attempts_per_slot", num(e.target.value, 1, 20))} />
          </Field>
          <Field label="Jeda antar akun (detik)" hint="Beri waktu proxy rotating ganti IP (0–600)">
            <input type="number" min={0} max={600} className={input} value={draft.delay_between_accounts}
              onChange={(e) => set("delay_between_accounts", num(e.target.value, 0, 600))} />
          </Field>
          <Field label="Simpan run (hari)" hint="Run lebih tua dari ini dihapus otomatis; 0 = simpan selamanya">
            <input type="number" min={0} max={3650} className={input} value={draft.retention_days}
              onChange={(e) => set("retention_days", num(e.target.value, 0, 3650))} />
          </Field>
        </div>
        <Fieldset legend="Debug" className="mt-4">
          <Switch label="Screenshot debug" desc="Simpan screenshot tiap langkah ke backend/result/ (hemat disk: matikan di produksi)" checked={draft.debug_screenshots} onChange={(e) => set("debug_screenshots", e.target.checked)} />
        </Fieldset>
      </Card>

      <Card
        title="Info Engine"
        desc="Dari env/file backend (read-only; ubah di .env lalu restart)"
        actions={summary ? <Pill tone={summary.flow_implemented ? "success" : "warn"} dot>{summary.flow_implemented ? "Flow siap" : "Flow stub"}</Pill> : undefined}
      >
        <div className="box !gap-0 !py-1">
          <KV k="Proxy" v={summary ? `${summary.proxies.total} di list · ${summary.proxies.bad} blacklist${summary.proxies.croxy ? " · Croxy rotating" : ""}` : "—"} />
          <KV k="Domain webhook" v={summary ? `${summary.domains.total} aktif · ${summary.domains.banned} banned` : "—"} />
          <KV k="Batch berikutnya" v={summary?.scheduler.next_run_at ? `${fmtDateTime(summary.scheduler.next_run_at)} WIB` : "nonaktif"} />
          <KV k="Isi ulang berikutnya" v={summary?.scheduler.next_refill_at ? `${fmtDateTime(summary.scheduler.next_refill_at)} WIB` : "nonaktif"} />
          <KV k="CONFIG_VERSION" v={<span className="font-mono">{settings.config_version}</span>} />
        </div>
        <p className="caption text-text3 mt-3">PROXY_LIST, CROXY_BASE_PROXY, CUSTOM_DOMAINS/domain.txt, kredensial provider email, dan KLING_DEFAULT_PASSWORD hanya dari <span className="font-mono">.env</span>.</p>
      </Card>

      <div className="card-actions !mt-0">
        {dirty && <span className="caption t-warn">Perubahan belum disimpan</span>}
        <Button variant="outlined" disabled={!dirty} onClick={() => setDraft(toDraft(settings))}>Batal</Button>
        <Button variant="primary" icon="save" spin={saving} disabled={saving || !dirty} onClick={save}>
          {saving ? "Menyimpan…" : dirty ? "Simpan Perubahan" : "Tersimpan"}
        </Button>
      </div>
    </div>
  );
}
