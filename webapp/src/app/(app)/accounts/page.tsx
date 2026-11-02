"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, FlashMsg } from "@/components/Alert";
import { Button, Card, Loading, PageBar, Pill } from "@/components/ui";
import { Empty } from "@/components/Empty";
import { FilterChip } from "@/components/bits";
import { useConfirm } from "@/components/Dialog";
import { AccountDialog } from "@/components/AccountDialog";
import { useIsAdmin } from "@/components/Shell";
import { Icon } from "@/components/Icon";
import { apiGet, apiPost, fmtDateTime, type AccountStatus, type AccountsPage } from "@/lib/api";
import { idFull } from "@/lib/format";

const SIZE = 50;
type Usage = "unused" | "used" | "unusable";
const USAGE_TAGS: { key: Usage; icon: string; label: string; cls: string; statuses: AccountStatus[] }[] = [
  { key: "unused", icon: "radio_button_unchecked", label: "Belum dipakai", cls: "text-success", statuses: ["pending", "standby", "active"] },
  { key: "used", icon: "task_alt", label: "Sudah dipakai", cls: "text-text3", statuses: ["used"] },
  { key: "unusable", icon: "block", label: "Tidak bisa dipakai", cls: "text-err", statuses: ["exhausted", "banned", "failed"] },
];

/** 3 tag pemakaian, ikon Material saja (label lewat title/aria-label): belum dipakai · sudah dipakai · tidak bisa dipakai. */
function UsageIcon({ status }: { status: AccountStatus }) {
  const tag = status === "used" ? { icon: "task_alt", cls: "text-text3", label: "Sudah dipakai" }
    : status === "failed" || status === "banned" || status === "exhausted" ? { icon: "block", cls: "text-err", label: `Tidak bisa dipakai (${status})` }
    : { icon: "radio_button_unchecked", cls: "text-success", label: `Belum dipakai (${status})` };
  return (
    <span className={`inline-flex ${tag.cls}`} title={tag.label} aria-label={tag.label} role="img">
      <Icon name={tag.icon} />
    </span>
  );
}

type BulkResult = { ok: boolean; action: string; affected: number };

export default function AccountsPage() {
  const confirm = useConfirm();
  const isAdmin = useIsAdmin();
  const [usage, setUsage] = useState<Usage | "">("");
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AccountsPage | null | undefined>(undefined);
  const [selected, setSelected] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setQDebounced(q.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), size: String(SIZE) });
    if (usage) p.set("usage", usage);
    if (qDebounced) p.set("q", qDebounced);
    return apiGet<AccountsPage>(`/accounts?${p}`).then(setData);
  }, [usage, qDebounced, page]);

  useEffect(() => { load(); }, [load]);

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / SIZE));
  const allCount = data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0;
  const pageIds = useMemo(() => (data?.items ?? []).map((a) => a.id), [data]);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => checked.has(id));
  const idsParam = checked.size > 0 ? `ids=${Array.from(checked).join(",")}` : usage ? `usage=${usage}` : "";
  const exportQs = idsParam ? `?${idsParam}` : "";
  const usageLabel = USAGE_TAGS.find((t) => t.key === usage)?.label.toLowerCase();
  const exportLabel = checked.size > 0 ? `${checked.size} terpilih` : usageLabel ?? "semua";
  const groupCount = (t: (typeof USAGE_TAGS)[number]) => (data ? t.statuses.reduce((n, st) => n + (data.counts[st] ?? 0), 0) : 0);

  const toggle = (id: number) => setChecked((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const toggleAll = () => setChecked((prev) => {
    const n = new Set(prev);
    if (allOnPage) pageIds.forEach((id) => n.delete(id)); else pageIds.forEach((id) => n.add(id));
    return n;
  });

  const flash = (ok: boolean, text: string) => { setMsg({ ok, text }); setTimeout(() => setMsg(null), 5000); };

  const bulk = async (action: "mark_used" | "mark_unused" | "delete") => {
    const ids = Array.from(checked);
    if (ids.length === 0) return;
    if (action === "delete" && !(await confirm({
      title: `Hapus ${ids.length} akun?`,
      body: "Baris akun dan cookies-nya di database dihapus permanen. Export dulu kalau masih perlu.",
      confirmLabel: "Hapus", danger: true,
    }))) return;
    setBusy(true);
    const r = await apiPost<BulkResult>("/accounts/bulk", { ids, action });
    setBusy(false);
    if (r.data) {
      const label = action === "mark_used" ? "ditandai sudah dipakai" : action === "mark_unused" ? "ditandai belum dipakai (standby)" : "dihapus";
      flash(true, `${r.data.affected} akun ${label}`);
      setChecked(new Set());
      await load();
    } else flash(false, r.error ?? "Aksi gagal");
  };

  return (
    <>
      <PageBar
        meta={data ? `${idFull(total)} akun${usageLabel ? ` · ${usageLabel}` : ""}${qDebounced ? ` · cari "${qDebounced}"` : ""} · centang untuk ${isAdmin ? "aksi massal" : "tandai dipakai / export"}, klik baris untuk detail` : "Memuat…"}
        right={
          <>
            <span className="caption text-text3 hidden sm:inline">Export {exportLabel}:</span>
            <Button variant="outlined" size="sm" icon="table_view" href={`/api/backend/accounts/export.xlsx${exportQs}`} download>Excel</Button>
            <Button variant="outlined" size="sm" icon="csv" href={`/api/backend/accounts/export.csv${exportQs}`} download>CSV</Button>
            <Button variant="outlined" size="sm" icon="data_object" href={`/api/backend/accounts/export.json${exportQs}`} download>JSON</Button>
          </>
        }
      />
      <FlashMsg msg={msg} />

      <Card padSm>
        <div className="flex flex-wrap items-center gap-2">
          {USAGE_TAGS.map((t) => {
            const active = usage === t.key;
            return (
              <span key={t.key} title={t.label}>
                <FilterChip active={active} onClick={() => { setUsage(active ? "" : t.key); setPage(1); }}>
                  <span className={`inline-flex items-center gap-1 ${active ? "" : t.cls}`} aria-label={t.label}>
                    <Icon name={t.icon} size="sm" />
                    <span className="tnum">{groupCount(t)}</span>
                  </span>
                </FilterChip>
              </span>
            );
          })}
          <input
            className="input compact w-full sm:w-auto sm:ml-auto sm:min-w-[220px] sm:max-w-xs"
            placeholder="Cari email / user id…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </Card>

      {checked.size > 0 && (
        <Card padSm className="!border-secondary">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="violet">{checked.size} akun dipilih</Pill>
            <Button variant="outlined" size="sm" icon="task_alt" disabled={busy} onClick={() => bulk("mark_used")}>Tandai sudah dipakai</Button>
            <Button variant="outlined" size="sm" icon="undo" disabled={busy} onClick={() => bulk("mark_unused")}>Tandai belum dipakai</Button>
            {isAdmin && <Button variant="danger" size="sm" icon="delete" disabled={busy} onClick={() => bulk("delete")}>Hapus</Button>}
            <Button variant="text" size="sm" onClick={() => setChecked(new Set())}>Batal pilih</Button>
          </div>
        </Card>
      )}

      {data === undefined ? (
        <Loading />
      ) : data === null ? (
        <Alert tone="err" title="Backend tidak dapat dihubungi">Daftar akun tidak bisa dimuat.</Alert>
      ) : data.items.length === 0 ? (
        <Card><Empty what="akun" icon="badge" hint={usage || qDebounced ? "Tidak ada akun yang cocok dengan filter." : "Akun muncul setelah run pertama berhasil membuat akun."} /></Card>
      ) : (
        <Card pad0 className="overflow-hidden">
          <div className="overflow-x-auto">
            <table style={{ minWidth: 760 }}>
              <thead>
                <tr>
                  <th className="w-10">
                    <input type="checkbox" className="checkbox" checked={allOnPage} onChange={toggleAll} aria-label="Pilih semua di halaman ini" />
                  </th>
                  <th>Email</th>
                  <th>Password</th>
                  <th className="w-16 text-center" title="belum dipakai / sudah dipakai / tidak bisa dipakai">Dipakai</th>
                  <th>Dibuat</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id} onClick={() => setSelected(a.id)} className={`cursor-pointer ${selected === a.id || checked.has(a.id) ? "selected" : ""}`}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" className="checkbox" checked={checked.has(a.id)} onChange={() => toggle(a.id)} aria-label={`Pilih ${a.email}`} />
                    </td>
                    <td className="font-semibold text-text font-mono text-[12.5px]">{a.email}</td>
                    <td className="font-mono text-[12.5px] text-text2">{a.password || "—"}</td>
                    <td className="text-center"><UsageIcon status={a.status} /></td>
                    <td className="text-text2 tnum">{fmtDateTime(a.created_at)}</td>
                    <td className={`caption max-w-[240px] truncate ${a.error ? "text-err" : "text-text3"}`} title={a.error ?? ""}>{a.error ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {data && pages > 1 && (
        <div className="flex items-center justify-between gap-3">
          <span className="caption text-text3">Halaman {page} dari {pages}</span>
          <div className="flex gap-2">
            <Button variant="outlined" size="sm" icon="chevron_left" disabled={page <= 1} onClick={() => setPage(page - 1)}>Sebelumnya</Button>
            <Button variant="outlined" size="sm" icon="chevron_right" disabled={page >= pages} onClick={() => setPage(page + 1)}>Berikutnya</Button>
          </div>
        </div>
      )}

      <AccountDialog accountId={selected} onClose={() => setSelected(null)} onChanged={load} />
    </>
  );
}
