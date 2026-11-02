"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { ConfirmProvider } from "./Dialog";
import type { Summary } from "@/lib/api";
import type { UserRole } from "@/lib/auth";

const RoleCtx = createContext<UserRole>("member");
/** Role sesi saat ini (dari middleware, dicek live ke backend). */
export function useRole(): UserRole {
  return useContext(RoleCtx);
}
export function useIsAdmin(): boolean {
  return useContext(RoleCtx) === "admin";
}

/** Kerangka app: sidebar (drawer di <1200px) + topbar + konten. */
export function Shell({ user, role = "member", summary, children }: { user?: string; role?: UserRole; summary: Summary | null; children: ReactNode }) {
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
    <RoleCtx.Provider value={role}>
      <ConfirmProvider>
        <Sidebar open={open} user={user} summary={summary} />
        {open && <div className="drawer-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />}
        <Topbar onMenu={() => setOpen(true)} menuOpen={open} summary={summary} />
        <main className="app-main">
          <div className="content">{children}</div>
        </main>
      </ConfirmProvider>
    </RoleCtx.Provider>
  );
}
