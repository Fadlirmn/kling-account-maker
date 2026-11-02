"use client";

import { useEffect, useState } from "react";
import { Card, Loading, PageBar, Pill } from "@/components/ui";
import { Alert } from "@/components/Alert";
import { Empty } from "@/components/Empty";
import { StopRunButton } from "@/components/StopRunButton";
import { LogView } from "@/components/LogView";
import { apiGet, fmtDateTime, relTime, type Run, type Summary } from "@/lib/api";

/** Konsol log creator: hanya log yang sedang / terakhir berjalan, live. Tanpa daftar run. */
export default function Logs() {
  const [runs, setRuns] = useState<Run[] | null | undefined>(undefined);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      apiGet<Run[]>("/runs?limit=1").then((d) => alive && setRuns(d));
      apiGet<Summary>("/summary").then((s) => alive && setSummary(s));
    };
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const current = runs && runs.length > 0 ? runs[0] : null;
  const running = summary?.creator_running ?? current?.status === "running";

  return (
    <>
      <PageBar
        meta={running ? "Creator sedang berjalan · log diperbarui tiap 5 detik" : current ? `Idle · aktivitas terakhir ${relTime(current.finished_at ?? current.started_at)}` : "Idle"}
        right={running ? <StopRunButton stopping={summary?.stop_requested} /> : undefined}
      />

      {summary && !summary.flow_implemented && (
        <Alert tone="warn" compact>
          Flow signup kling.ai masih stub — batch berakhir <span className="font-mono text-[12px]">NOT_IMPLEMENTED</span> setelah slot pertama.
        </Alert>
      )}

      {runs === undefined ? (
        <Loading />
      ) : !current ? (
        <Card><Empty what="log creator" icon="terminal" hint="Log muncul di sini saat batch pertama berjalan (jadwal / isi ulang di Settings)." /></Card>
      ) : (
        <Card
          pad0
          className="overflow-hidden"
          title={
            <span className="flex items-center gap-2">
              Log creator
              {running ? <Pill sm tone="info" pulse>berjalan</Pill> : <Pill sm tone={current.status === "failed" ? "err" : current.status === "partial" ? "warn" : "success"}>{current.status === "failed" ? "gagal" : current.status === "partial" ? "sebagian" : "selesai"}</Pill>}
            </span>
          }
          desc={`${fmtDateTime(current.started_at)} WIB · ${current.created_ok} akun dibuat · ${current.failed} gagal`}
        >
          <div className="px-4 pb-4">
            {current.error_message && (
              <Alert tone="err" compact className="mb-3">
                <span className="font-mono text-[12px]">{current.error_message}</span>
              </Alert>
            )}
            <LogView key={current.id} runId={current.id} status={current.status} initialLog={null} maxHeight={640} />
          </div>
        </Card>
      )}
    </>
  );
}
