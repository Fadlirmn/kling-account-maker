"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { linkActive, SETTINGS_TABS } from "./nav";

export function SettingsTabs() {
  const path = usePathname();
  return (
    <nav className="tabs" aria-label="Bagian settings">
      {SETTINGS_TABS.map((t) => {
        const active = linkActive(t, path);
        return (
          <Link key={t.href} href={t.href} className={`tab ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
            <Icon name={t.icon} size="md" />
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
