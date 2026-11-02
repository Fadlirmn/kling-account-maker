"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { ConfirmProvider } from "./Dialog";
import type { Summary } from "@/lib/api";

/** Kerangka app: sidebar (drawer di ≤860px) + topbar + konten. */
export function Shell({ user, summary, children }: { user?: string; summary: Summary | null; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const path = usePathname();

  // tutup drawer saat pindah halaman
  useEffect(() => setOpen(false), [path]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <ConfirmProvider>
      <Sidebar open={open} user={user} summary={summary} />
      {open && <div className="drawer-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />}
      <Topbar onMenu={() => setOpen(true)} menuOpen={open} summary={summary} />
      <main className="app-main">
        <div className="content">{children}</div>
      </main>
    </ConfirmProvider>
  );
}
