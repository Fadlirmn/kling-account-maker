"use client";

import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { Pill } from "./ui";
import { StopRunButton } from "./StopRunButton";
import { pageMeta } from "./nav";
import { useIsAdmin } from "./Shell";
import type { Summary } from "@/lib/api";

export function Topbar({ onMenu, menuOpen, summary }: { onMenu: () => void; menuOpen: boolean; summary: Summary | null }) {
  const path = usePathname();
  const { title, sub } = pageMeta(path);
  const isAdmin = useIsAdmin();
  const run = summary?.last_run ?? null;
  const running = summary?.creator_running ?? false;
  const target = summary?.standby_target ?? 0;
  const standbyOk = !summary || target === 0 || summary.standby >= target;

  return (
    <header className="topbar">
      <div className="left">
        <button
          type="button"
          className="iconbtn btn-menu"
          onClick={onMenu}
          aria-label="Buka menu"
          aria-controls="sidebar"
          aria-expanded={menuOpen}
        >
          <Icon name="menu" />
        </button>
        <div className="flex flex-col min-w-0 gap-px">
          <h1 className="h5 el">{title}</h1>
          <span className="caption page-sub el">{sub}</span>
        </div>
      </div>
      <div className="right">
        <div className="hidden xl:flex items-center gap-2">
          {summary === null ? (
            <Pill tone="err" dot>Backend: Offline</Pill>
          ) : (
            <>
              <Pill tone={standbyOk ? "success" : "warn"} dot>
                Standby: {summary.standby}{target > 0 && ` / ${target}`}
              </Pill>
              {run && (
                <Pill tone={run.status === "failed" ? "err" : run.status === "success" ? "success" : run.status === "running" ? "info" : "warn"} pulse={run.status === "running"}>
                  Last Run: {run.status}
                </Pill>
              )}
            </>
          )}
        </div>
        {isAdmin && running && <StopRunButton stopping={summary?.stop_requested} compact />}
      </div>
    </header>
  );
}
