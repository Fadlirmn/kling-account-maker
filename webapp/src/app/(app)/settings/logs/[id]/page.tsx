import { Button, Card, KV, PageBar, Pill, TableWrap, type Tone } from "@/components/ui";
import { Alert } from "@/components/Alert";
import { Empty } from "@/components/Empty";
import { StatusPill } from "@/components/AccountDialog";
import { apiGet, durationMin, fmtDateTime, TRIGGER_LABEL, type Run } from "@/lib/api";
import { LogView } from "@/components/LogView";

const tone = (s: Run["status"]): Tone => (s === "success" ? "success" : s === "failed" ? "err" : s === "running" ? "info" : "warn");

export default async function RunDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = /^\d+$/.test(id) ? await apiGet<Run>(`/runs/${id}`) : null;

  if (!run) {
    return (
      <>
        <PageBar meta={`Run #${id} · tidak ditemukan`} right={<Button variant="outlined" size="sm" href="/settings/logs" icon="arrow_back">Logs</Button>} />
        <Alert tone="warn">Run tidak ada atau backend tidak dapat dihubungi.</Alert>
      </>
    );
  }

  const d = durationMin(run);
  const accounts = run.accounts ?? [];
  const rows: Array<[string, React.ReactNode]> = [
    ["Status", <Pill key="s" sm tone={tone(run.status)} pulse={run.status === "running"}>{run.status}</Pill>],
    ["Trigger", TRIGGER_LABEL[run.trigger] ?? run.trigger],
    ["Mulai", `${fmtDateTime(run.started_at)} WIB`],
    ["Selesai", run.finished_at ? `${fmtDateTime(run.finished_at)} WIB` : "—"],
    ["Durasi", d === null ? "—" : `${d} menit`],
    ["Slot diminta", `${run.requested} akun`],
    ["Worker", `${run.workers} browser paralel`],
    ["Provider email", run.provider ?? "—"],
    ["Berhasil", `${run.created_ok} akun`],
    ["Gagal", `${run.failed} slot`],
    ["Dilewati", `${run.skipped} slot`],
    ["Config version", `v${run.config_version}`],
  ];

  return (
    <>
      <PageBar
        meta={`Run #${run.id} · ${fmtDateTime(run.started_at)} WIB · ${TRIGGER_LABEL[run.trigger] ?? run.trigger}`}
        right={
          <>
            <Button variant="outlined" size="sm" href="/settings/logs" icon="arrow_back">Logs</Button>
            {accounts.length > 0 && <Button variant="outlined" size="sm" href="/accounts" icon="badge">Semua akun</Button>}
          </>
        }
      />

      {run.error_message && (
        <Alert tone="err" title="Error">
          <span className="font-mono text-[12px]">{run.error_message}</span>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title={`Run #${run.id}`} desc="Ringkasan">
          {rows.map(([k, v]) => (
            <KV key={k} k={k} v={v} />
          ))}
        </Card>
        <Card title="Log" desc="Catatan langkah creator per slot untuk run ini" className="lg:col-span-2">
          <LogView runId={run.id} status={run.status} initialLog={run.log} maxHeight={560} />
        </Card>
      </div>

      <Card title="Akun di run ini" desc={`${accounts.length} akun tercatat (berhasil maupun gagal)`}>
        {accounts.length === 0 ? (
          <Empty what="akun run ini" icon="badge" hint="Run belum menghasilkan akun." />
        ) : (
          <TableWrap>
            <table>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Status</th>
                  <th>User ID</th>
                  <th>Provider</th>
                  <th className="tr">Attempt</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id}>
                    <td className="font-mono text-[12.5px] text-text font-semibold">{a.email}</td>
                    <td><StatusPill status={a.status} /></td>
                    <td className="text-text2 font-mono text-[12px]">{a.user_id || "—"}</td>
                    <td><Pill sm>{a.email_mode || "—"}</Pill></td>
                    <td className="tr tnum text-text2">{a.attempts}</td>
                    <td className={`caption max-w-[260px] truncate ${a.error ? "text-err" : "text-text3"}`} title={a.error ?? ""}>{a.error ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </>
  );
}
