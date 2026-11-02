"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { Button } from "./ui";
import { useConfirm } from "./Dialog";

/** Minta batch berhenti: slot baru tidak dimulai; attempt yang sedang jalan diselesaikan dulu. */
export function StopRunButton({ stopping = false, compact = false }: { stopping?: boolean; compact?: boolean }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  const stop = async () => {
    const ok = await confirm({
      title: "Hentikan batch yang berjalan?",
      body: "Slot yang belum mulai dibatalkan. Browser yang sedang membuat akun diselesaikan dulu (±1–3 menit).",
      confirmLabel: "Hentikan",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    await apiPost("/runs/stop");
    setBusy(false);
    router.refresh();
  };

  return (
    <Button variant="danger" size={compact ? "sm" : "md"} icon="stop" spin={busy || stopping} disabled={busy || stopping} onClick={stop} title="Hentikan batch">
      <span className={compact ? "hidden sm:inline" : ""}>{stopping ? "Menghentikan…" : "Stop"}</span>
    </Button>
  );
}
