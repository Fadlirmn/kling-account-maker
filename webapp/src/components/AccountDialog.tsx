"use client";

import { useEffect, useState } from "react";
import { Alert } from "./Alert";
import { Dialog, useConfirm } from "./Dialog";
import { Field, Select } from "./form";
import { Button, IconButton, KV, Pill, type Tone } from "./ui";
import { ACCOUNT_STATUSES, apiGet, apiPut, fmtDateTime, type Account, type AccountStatus } from "@/lib/api";
import { useIsAdmin } from "./Shell";

export const STATUS_TONE: Record<AccountStatus, Tone> = {
  pending: "neutral", standby: "success", active: "info", exhausted: "warn", used: "neutral", banned: "err", failed: "err",
};

export function StatusPill({ status, sm = true }: { status: AccountStatus; sm?: boolean }) {
  return <Pill tone={STATUS_TONE[status] ?? "neutral"} sm={sm}>{status}</Pill>;
}

/** Detail satu akun + ubah status + unduh cookies. */
export function AccountDialog({ accountId, onClose, onChanged }: { accountId: number | null; onClose: () => void; onChanged?: () => void }) {
  const confirm = useConfirm();
  const isAdmin = useIsAdmin();
  const [acc, setAcc] = useState<Account | null | undefined>(undefined);
  const [status, setStatus] = useState<AccountStatus>("standby");
  const [showPw, setShowPw] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (accountId === null) { setAcc(undefined); return; }
    let alive = true;
    setAcc(undefined); setShowPw(false); setMsg(null);
    apiGet<Account>(`/accounts/${accountId}`).then((a) => { if (alive) { setAcc(a); if (a) setStatus(a.status); } });
    return () => { alive = false; };
  }, [accountId]);

  const save = async () => {
    if (!acc) return;
    if (status === "banned" && !(await confirm({ title: `Tandai ${acc.email} sebagai banned?`, body: "Akun tidak akan dipakai lagi. Status bisa diubah kembali nanti.", confirmLabel: "Tandai banned", danger: true }))) return;
    setSaving(true);
    const r = await apiPut<Account>(`/accounts/${acc.id}/status`, { status });
    if (r.data) { setAcc(r.data); setMsg({ ok: true, text: `Status → ${r.data.status}` }); onChanged?.(); }
    else setMsg({ ok: false, text: r.error ?? "Gagal menyimpan status" });
    setSaving(false);
    setTimeout(() => setMsg(null), 4000);
  };

  return (
    <Dialog
      open={accountId !== null}
      onClose={onClose}
      size="lg"
      block
      title={<span className="flex items-center gap-2 min-w-0"><span className="truncate">{acc ? acc.email : `Akun #${accountId}`}</span>{acc && <StatusPill status={acc.status} />}</span>}
      actions={
        <>
          {acc && <Button variant="outlined" icon="download" href={`/api/backend/accounts/${acc.id}/cookies`} download disabled={!acc.has_cookies}>Download cookies</Button>}
          <Button variant="outlined" onClick={onClose}>Tutup</Button>
        </>
      }
    >
      {acc === undefined ? (
        <p className="body2 text-text2 py-6 text-center">Memuat detail akun…</p>
      ) : acc === null ? (
        <Alert tone="err">Akun tidak ditemukan atau backend tidak dapat dihubungi.</Alert>
      ) : (
        <>
          {msg && <Alert tone={msg.ok ? "success" : "err"} compact>{msg.text}</Alert>}
          {acc.error && <Alert tone="err" title="Error terakhir" compact><span className="font-mono text-[12px]">{acc.error}</span></Alert>}
          <div className="box !gap-0 !py-1">
            <KV k="Email" v={<span className="font-mono text-[12.5px] break-all">{acc.email}</span>} />
            <KV
              k="Password"
              v={
                <span className="inline-flex items-center gap-1 font-mono text-[12.5px]">
                  {showPw ? acc.password || "—" : "••••••••"}
                  <IconButton name={showPw ? "visibility_off" : "visibility"} label={showPw ? "Sembunyikan" : "Tampilkan"} xs onClick={() => setShowPw(!showPw)} />
                </span>
              }
            />
            <KV k="User ID" v={acc.user_id || "—"} />
            <KV k="OTP terakhir" v={acc.otp || "—"} />
            <KV k="Provider email" v={acc.email_mode || "—"} />
            <KV k="Proxy" v={<span className="font-mono text-[12px] break-all">{acc.proxy || "— (direct)"}</span>} />
            <KV k="Attempt" v={acc.attempts} />
            <KV k="Credits / plan" v={`${acc.credits || "—"} / ${acc.plan || "—"}`} />
            <KV k="Run" v={acc.run_id ? (isAdmin ? <Button variant="text" size="sm" href={`/settings/logs/${acc.run_id}`} icon="terminal" className="-ml-2 h-7">#{acc.run_id}</Button> : `#${acc.run_id}`) : "—"} />
            <KV k="Dibuat" v={`${fmtDateTime(acc.created_at)} WIB`} />
            <KV k="Diubah" v={`${fmtDateTime(acc.updated_at)} WIB`} />
            <KV k="Cookies" v={acc.has_cookies ? "tersimpan" : "tidak ada"} />
          </div>
          {isAdmin && <div className="flex flex-wrap items-end gap-3 mt-2">
            <Field label="Ubah status" className="flex-1 min-w-[180px]">
              <Select value={status} onChange={(e) => setStatus(e.target.value as AccountStatus)}>
                {ACCOUNT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </Field>
            <Button variant="primary" icon="save" spin={saving} disabled={saving || status === acc.status} onClick={save}>Simpan status</Button>
          </div>}
        </>
      )}
    </Dialog>
  );
}
