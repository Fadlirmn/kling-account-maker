"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef } from "react";
import { Icon } from "./Icon";
import { Avatar, IconButton, Pill } from "./ui";
import { ThemeToggle } from "./ThemeToggle";
import { useConfirm } from "./Dialog";
import { linkActive, NAV_SECTIONS } from "./nav";
import { useRole } from "./Shell";
import { fmtDateTime, relTime, type Summary } from "@/lib/api";

export function Sidebar({ open, user = "admin", summary }: { open: boolean; user?: string; summary: Summary | null }) {
  const path = usePathname();
  const confirm = useConfirm();
  const role = useRole();
  const isAdmin = role === "admin";
  const sections = isAdmin
    ? NAV_SECTIONS
    : NAV_SECTIONS.map((s) => ({ ...s, items: s.items.filter((l) => l.href === "/accounts") })).filter((s) => s.items.length > 0);
  const logoutForm = useRef<HTMLFormElement>(null);

  const run = summary?.last_run ?? null;
  const running = summary?.creator_running ?? false;
  const sched = summary?.scheduler;

  const logout = async () => {
    if (!(await confirm({ title: "Keluar dari console?", body: "Sesi login di browser ini akan diakhiri.", confirmLabel: "Keluar" }))) return;
    logoutForm.current?.submit();
  };

  return (
    <aside className={`sidebar ${open ? "open" : ""}`} id="sidebar" aria-label="Navigasi">
      <div className="sb-head">
        <Image src="/logo/kling-icon.svg" alt="Kling Account Maker" width={46} height={46} priority />
        <div className="flex flex-col min-w-0 gap-px">
          <span className="sb-title el">Kurma Kling</span>
          <span className="sb-tag el">Account Maker</span>
        </div>
      </div>

      <nav className="sb-nav">
        {sections.map((s) => (
          <div key={s.label} className="contents">
            <span className="nav-section">{s.label}</span>
            {s.items.map((l) => {
              const active = linkActive(l, path);
              return (
                <Link key={l.href} href={l.href} className={`nav-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
                  <Icon name={l.icon} />
                  {l.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sb-daemon">
        <div className="flex items-center justify-between gap-2">
          <span className="subtitle2 nav-sub">Creator</span>
          {summary === null ? (
            <Pill tone="err" sm>Offline</Pill>
          ) : running ? (
            <Pill tone="success" sm pulse>{summary.stop_requested ? "Stopping" : "Running"}</Pill>
          ) : (
            <Pill sm>Idle</Pill>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 caption">
          <span>Run terakhir</span>
          <span className="tnum el">{run ? `#${run.id} · ${relTime(run.finished_at ?? run.started_at)}` : "—"}</span>
        </div>
        <div className="flex items-center justify-between gap-2 caption">
          <span>Standby</span>
          <span className="tnum el">{summary ? `${summary.standby} / ${summary.standby_target || "∞"}` : "—"}</span>
        </div>
        <div className="flex items-center justify-between gap-2 caption">
          <span>Jadwal</span>
          <span className="tnum el">{sched ? (sched.enabled ? fmtDateTime(sched.next_run_at) : "nonaktif") : "—"}</span>
        </div>
      </div>

      <div className="sb-footer">
        <Link href={isAdmin ? "/settings/users" : "/accounts"} className="sb-user" title={isAdmin ? "Akun dashboard" : "Distribusi akun"}>
          <Avatar name={user} />
          <span className="flex flex-col min-w-0">
            <span className="sb-name el">{user}</span>
            <span className="caption el">{isAdmin ? "Administrator" : "Member · distribusi akun"}</span>
          </span>
        </Link>
        <ThemeToggle />
        <IconButton name="logout" label="Keluar" nav onClick={logout} />
        <form ref={logoutForm} method="post" action="/api/auth/logout" className="hidden" />
      </div>
    </aside>
  );
}
