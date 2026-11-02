"use client";

import { useEffect, useState } from "react";
import { apiGet, type RunLog, type RunStatus } from "@/lib/api";
import { Button } from "./ui";

const LEVEL = /^\[\d\d:\d\d:\d\d\] \[\+[\d.]+s\] (INFO|WARN|ERROR|STAGE)/;

function lineClass(line: string): string {
  const level = LEVEL.exec(line)?.[1];
  if (level === "ERROR") return "lv-ERROR";
  if (level === "WARN") return "lv-WARN";
  if (level === "STAGE") return "lv-STAGE";
  if (line.startsWith("===")) return "lv-STAGE";
  if (!level && line.trim()) return "lv-DEBUG"; // lanjutan traceback
  return "lv-INFO";
}

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // clipboard API hanya ada di secure context (https/localhost) — fallback lama
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

/** Log satu run; saat status running di-poll tiap 5 detik dari file log backend. */
export function LogView({ runId, status, initialLog, maxHeight = 360 }: {
  runId: number;
  status?: RunStatus;
  initialLog?: string | null;
  maxHeight?: number;
}) {
  const [data, setData] = useState<RunLog | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => apiGet<RunLog>(`/runs/${runId}/log`).then((d) => alive && d && setData(d));
    load();
    if (status !== "running") return () => { alive = false; };
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, [runId, status]);

  const text = data?.log ?? initialLog ?? "";
  const lines = text ? text.split("\n") : [];

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="subtitle2">
          Output log creator
          {data?.source === "file" && status === "running" && " · live"}
          {data?.truncated && " · dipotong"}
        </span>
        {text && (
          <Button
            variant="text"
            size="sm"
            icon={copied ? "check" : "content_copy"}
            className={copied ? "!text-success" : ""}
            onClick={async () => {
              if (!(await copy(text))) return;
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? "Tersalin!" : "Salin Log"}
          </Button>
        )}
      </div>
      {lines.length > 0 ? (
        <div className="console" style={{ maxHeight }}>
          <div className="viewport">
            {lines.map((l, i) => (
              <div key={i} className={`logrow ${lineClass(l)}`}>{l || "\u00a0"}</div>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty">
          <span>{status === "running" ? "Menunggu baris log pertama…" : "Belum ada catatan log tertulis untuk run ini."}</span>
        </div>
      )}
    </div>
  );
}
