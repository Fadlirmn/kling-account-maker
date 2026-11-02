export type NavLink = {
  href: string;
  label: string;
  /** nama ikon Material Symbols */
  icon: string;
  /** judul di topbar (default: label) */
  title?: string;
  /** subjudul di topbar */
  sub: string;
  /** subjudul saat berada di sub-route (mis. /settings/logs/12) */
  detailSub?: string;
  exact?: boolean;
};
export type NavSection = { label: string; items: NavLink[] };

export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Operasi",
    items: [
      { href: "/", label: "Dashboard", icon: "grid_view", sub: "Ringkasan pool akun standby Kling", exact: true },
      { href: "/accounts", label: "Accounts", icon: "badge", sub: "Akun yang sudah dibuat, status, dan cookies", detailSub: "Detail akun" },
    ],
  },
  {
    label: "Sistem",
    items: [
      { href: "/settings", label: "Settings", icon: "tune", sub: "Jadwal, batch, provider email, log run, dan akun dashboard" },
    ],
  },
];

/** Tab di dalam halaman Settings (bukan item sidebar). */
export const SETTINGS_TABS: NavLink[] = [
  { href: "/settings", label: "Umum", icon: "tune", title: "Settings", sub: "Scheduler, batch, provider email, batas harian", exact: true },
  { href: "/settings/logs", label: "Logs", icon: "terminal", title: "Settings · Logs", sub: "Log creator saat ini (live)" },
  { href: "/settings/users", label: "User", icon: "group", title: "Settings · User", sub: "Akun dashboard" },
  { href: "/settings/testing", label: "Testing", icon: "science", title: "Settings · Testing", sub: "Uji di server: diagnostik, run manual, provider email" },
];

const ALL: NavLink[] = [...SETTINGS_TABS, ...NAV_SECTIONS.flatMap((s) => s.items).filter((l) => l.href !== "/settings")];

export function linkActive(link: NavLink, path: string): boolean {
  if (link.exact) return path === link.href;
  return path === link.href || path.startsWith(`${link.href}/`);
}

/** Judul + subjudul topbar untuk path saat ini (prefix terpanjang menang). */
export function pageMeta(path: string): { title: string; sub: string } {
  const exact = ALL.find((l) => l.href === path);
  if (exact) return { title: exact.title ?? exact.label, sub: exact.sub };
  const parent = ALL.filter((l) => l.href !== "/" && path.startsWith(`${l.href}/`)).sort((a, b) => b.href.length - a.href.length)[0];
  if (parent) return { title: parent.title ?? parent.label, sub: parent.detailSub ?? parent.sub };
  return { title: "Kurma Kling", sub: "Account Maker" };
}
