import { Alert } from "@/components/Alert";
import { Button, Card, Metric, Metrics, Pill, StatusDot, TableWrap } from "@/components/ui";
import { TrendChart, TrendLegend } from "@/components/TrendChart";
import { Empty } from "@/components/Empty";
import { StatusPill } from "@/components/AccountDialog";
import {
  ACCOUNT_STATUSES, apiGet, durationMin, fmtDateTime, relTime, TRIGGER_LABEL,
  type Run, type Summary, type TrendPoint,
} from "@/lib/api";
import { idFull } from "@/lib/format";

const runTone = (s: Run["status"]) => (s === "success" ? "success" : s === "failed" ? "err" : s === "running" ? "info" : "warn");

export default async function Dashboard() {
  const summary = await apiGet<Summary>("/summary");
  const [trend, runs] = summary
    ? await Promise.all([apiGet<TrendPoint[]>("/accounts/trend?days=14"), apiGet<Run[]>("/runs?limit=5")])
    : [null, null];
  const last = summary?.last_run ?? null;
  const dur = last ? durationMin(last) : null;
  const target = summary?.standby_target ?? 0;
  const hasTrend = !!trend && trend.some((p) => p.created > 0 || p.failed > 0);

  return (
    <>
      {summary === null && (
        <Alert tone="err" title="Backend tidak dapat dihubungi">
          Layanan API creator tidak merespons. Periksa container kling-backend (docker compose logs backend).
        </Alert>
      )}
      {summary && !summary.flow_implemented && (
        <Alert
          tone="warn"
          title="Flow signup kling.ai belum diimplementasi"
          actions={<Button variant="text" size="sm" href="/settings/logs" icon="terminal">Lihat run</Button>}
        >
          <code className="font-mono text-[12.5px]">backend/sites/kling/flow.py</code> masih stub — setiap batch berakhir
          <span className="font-mono text-[12.5px]"> NOT_IMPLEMENTED</span>. Infrastruktur (DB, proxy, email/OTP, browser) sudah siap;
          isi selector dan langkah signup lalu hapus <code className="font-mono text-[12.5px]">IS_STUB</code>.
        </Alert>
      )}
      {last?.status === "failed" && summary?.flow_implemented && (
        <Alert
          tone="err"
          title={`Run terakhir #${last.id} gagal`}
          actions={<Button variant="text" size="sm" href={`/settings/logs/${last.id}`} icon="terminal">Lihat log</Button>}
        >
          <span className="font-mono text-[12.5px]">{last.error_message ?? "tanpa pesan error"}</span>
        </Alert>
      )}
      {summary && summary.proxies.total === 0 && !summary.proxies.croxy && (
        <Alert tone="warn" title="Tanpa proxy">
          <code className="font-mono text-[12.5px]">PROXY_LIST</code> / <code className="font-mono text-[12.5px]">CROXY_BASE_PROXY</code> kosong — browser memakai IP server langsung.
          Isi di <code className="font-mono text-[12.5px]">.env</code> atau <code className="font-mono text-[12.5px]">backend/data/proxy.txt</code> lalu restart backend.
        </Alert>
      )}
      {summary && target > 0 && summary.standby < target && summary.flow_implemented && (
        <Alert tone="info" title="Pool standby di bawah target">
          Standby {summary.standby} dari target {target}. Isi ulang otomatis berjalan tiap interval di Settings, atau tekan Run Now.
        </Alert>
      )}

      <Metrics>
        <Metric
          label="Pool standby"
          value={summary ? idFull(summary.standby) : "—"}
          unit="akun"
          pill={summary && target > 0 ? <Pill sm tone={summary.standby >= target ? "success" : "warn"}>target {target}</Pill> : undefined}
          sub={summary ? `${idFull(summary.active)} active · ${idFull(summary.total)} total` : undefined}
        />
        <Metric
          label="Dibuat 24 jam"
          value={summary ? idFull(summary.created_24h) : "—"}
          unit="akun"
          sub={summary ? `${idFull(summary.created_today)} hari ini (WIB)` : undefined}
        />
        <Metric
          label="Gagal 24 jam"
          value={summary ? idFull(summary.failed_24h) : "—"}
          unit="slot"
          pill={summary && summary.failed_24h > 0 && summary.created_24h === 0 ? <Pill sm tone="err">perlu cek</Pill> : undefined}
          sub={summary ? `${summary.proxies.total} proxy (${summary.proxies.bad} blacklist) · ${summary.domains.total} domain` : undefined}
        />
        <Metric
          label={last ? `Run terakhir (#${last.id})` : "Run terakhir"}
          value={last ? relTime(last.finished_at ?? last.started_at) : "—"}
          pill={last ? <Pill sm tone={runTone(last.status)} pulse={last.status === "running"}>{last.status}</Pill> : undefined}
          sub={last ? (
            <span className="truncate" title={`${fmtDateTime(last.started_at)} WIB`}>
              {fmtDateTime(last.started_at)} WIB{dur !== null && <> · {dur}m</>} · <span className="text-text tnum">{last.created_ok}</span>/{last.requested} ok
            </span>
          ) : "Belum ada run. Tekan Run Now."}
        />
      </Metrics>

      <Card
        title="Akun dibuat per hari"
        desc="14 hari terakhir (WIB) · dibuat = standby/active, gagal = slot yang habis attempt"
        actions={hasTrend ? <div className="hidden sm:block"><TrendLegend /></div> : undefined}
      >
        {trend && hasTrend ? (
          <TrendChart data={trend} />
        ) : (
          <Empty what="tren pembuatan akun" hint="Grafik terisi setelah ada run yang menghasilkan akun." icon="monitoring" />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          title="Run terbaru"
          desc="5 batch terakhir"
          actions={runs && runs.length > 0 ? <Button variant="text" size="sm" href="/settings/logs" icon="arrow_forward">Semua run</Button> : undefined}
        >
          {runs && runs.length > 0 ? (
            <TableWrap>
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Mulai</th>
                    <th>Trigger</th>
                    <th>Status</th>
                    <th className="tr">OK / Gagal</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td className="font-bold text-text tnum">#{r.id}</td>
                      <td className="text-text2 tnum">{fmtDateTime(r.started_at)}</td>
                      <td><Pill sm>{TRIGGER_LABEL[r.trigger] ?? r.trigger}</Pill></td>
                      <td><Pill sm tone={runTone(r.status)} pulse={r.status === "running"}>{r.status}</Pill></td>
                      <td className="tr tnum text-text2"><span className="text-text">{r.created_ok}</span> / {r.failed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          ) : (
            <Empty what="riwayat run" icon="terminal" hint="Tekan Run Now untuk batch pertama." />
          )}
        </Card>

        <Card
          title="Komposisi status akun"
          desc="Semua akun di database"
          actions={summary && summary.total > 0 ? <Button variant="text" size="sm" href="/accounts" icon="arrow_forward">Lihat akun</Button> : undefined}
        >
          {summary && summary.total > 0 ? (
            <div className="divide-y divide-line-soft">
              {ACCOUNT_STATUSES.filter((s) => (summary.counts[s] ?? 0) > 0).map((s) => (
                <div key={s} className="flex items-center justify-between gap-3 py-2.5">
                  <StatusPill status={s} />
                  <span className="body2 text-text font-semibold tnum">{idFull(summary.counts[s])}</span>
                </div>
              ))}
            </div>
          ) : (
            <Empty what="akun" icon="badge" hint="Akun muncul setelah run pertama berhasil." />
          )}
        </Card>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 caption text-text3">
        <span className="flex items-center gap-1.5">
          <StatusDot tone={summary ? "success" : "err"} />
          {summary ? `Scheduler ${summary.scheduler.enabled ? `aktif · next ${fmtDateTime(summary.scheduler.next_run_at)} WIB` : "nonaktif"}` : "Backend offline"}
        </span>
        <span>{summary?.scheduler.next_refill_at ? `Isi ulang otomatis berikutnya ${fmtDateTime(summary.scheduler.next_refill_at)} WIB` : summary ? "Isi ulang otomatis nonaktif" : ""}</span>
        <span>{last ? `Run #${last.id} · ${fmtDateTime(last.started_at)} WIB · Config v${last.config_version}` : "Belum ada run"}</span>
      </div>
    </>
  );
}
