"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost, EMAIL_PROVIDERS, type EmailProvider, type Settings } from "@/lib/api";
import { Button } from "./ui";
import { Dialog } from "./Dialog";
import { Field, Select } from "./form";

const num = (v: string, lo: number, hi: number) => Math.max(lo, Math.min(hi, Number(v) || lo));

/** Tombol Run Now: buka dialog jumlah akun + worker, lalu POST /runs. */
export function RunNowButton({ running = false, compact = false }: { running?: boolean; compact?: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [count, setCount] = useState(10);
  const [workers, setWorkers] = useState(2);
  const [provider, setProvider] = useState<EmailProvider | "">("");

  const openDialog = async () => {
    setOpen(true);
    const s = await apiGet<Settings>("/settings");
    if (s) { setCount(s.batch_size); setWorkers(s.workers); }
  };

  const start = async () => {
    setBusy(true);
    setMsg(null);
    const body: Record<string, unknown> = { trigger: "manual", count, workers };
    if (provider) body.provider = provider;
    const r = await apiPost<{ started: boolean }>("/runs", body);
    if (r.status === 202) setMsg(`Batch ${count} akun dimulai`);
    else if (r.status === 409) setMsg("Creator sedang berjalan");
    else setMsg(r.error ?? "Gagal memulai batch");
    setBusy(false);
    setOpen(false);
    router.refresh();
    setTimeout(() => setMsg(null), 4000);
  };

  return (
    <span className="inline-flex items-center gap-2">
      {msg && <span className="caption text-text2 hidden sm:inline">{msg}</span>}
      <Button
        variant="primary"
        size={compact ? "sm" : "md"}
        icon={running ? "sync" : "play_arrow"}
        spin={running}
        disabled={busy || running}
        onClick={openDialog}
        title="Jalankan batch pembuatan akun sekarang"
      >
        <span className={compact ? "hidden sm:inline" : ""}>{running ? "Running…" : "Run Now"}</span>
      </Button>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Jalankan batch pembuatan akun"
        actions={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>Batal</Button>
            <Button variant="primary" icon="play_arrow" spin={busy} disabled={busy} onClick={start}>Mulai</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3.5">
          <Field label="Jumlah akun" hint="1–500 slot; dipotong otomatis oleh batas harian">
            <input type="number" min={1} max={500} className="input" value={count} onChange={(e) => setCount(num(e.target.value, 1, 500))} />
          </Field>
          <Field label="Worker (browser paralel)" hint="1–16; dibatasi RAM guard di server">
            <input type="number" min={1} max={16} className="input" value={workers} onChange={(e) => setWorkers(num(e.target.value, 1, 16))} />
          </Field>
          <Field label="Provider email" hint="Kosong = ikut Settings">
            <Select value={provider} onChange={(e) => setProvider(e.target.value as EmailProvider | "")}>
              <option value="">(ikut settings)</option>
              {EMAIL_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </Field>
        </div>
        <p className="caption text-text3">Hanya satu batch yang berjalan pada satu waktu. Progres tampil di Settings ▸ Logs.</p>
      </Dialog>
    </span>
  );
}
