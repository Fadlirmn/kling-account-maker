"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";

type Mode = "light" | "dark" | "system";

const ICON: Record<Mode, string> = { light: "light_mode", dark: "dark_mode", system: "brightness_auto" };
const LABEL: Record<Mode, string> = { light: "Tema: terang", dark: "Tema: gelap", system: "Tema: ikut sistem" };
const NEXT: Record<Mode, Mode> = { light: "dark", dark: "system", system: "light" };

// :root = terang; gelap = atribut data-theme="dark" (dihapus saat terang).
// Skema awal sudah dipasang skrip <head> (layout.tsx); di sini hanya siklus tombol + ikut perubahan OS.
function apply(mode: Mode) {
  const d = document.documentElement;
  d.dataset.themeMode = mode;
  const dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  if (dark) d.dataset.theme = "dark";
  else delete d.dataset.theme;
}

export function ThemeToggle({ variant = "nav" }: { variant?: "nav" | "plain" }) {
  const [mode, setMode] = useState<Mode>("system");

  useEffect(() => {
    const m = document.documentElement.dataset.themeMode as Mode | undefined;
    setMode(m === "light" || m === "dark" ? m : "system");
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (document.documentElement.dataset.themeMode === "system") apply("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const cycle = () => {
    const next = NEXT[mode];
    try {
      if (next === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", next);
    } catch {
      /* storage diblokir — tetap terapkan untuk sesi ini */
    }
    apply(next);
    setMode(next);
  };

  return (
    <button
      type="button"
      onClick={cycle}
      className={`iconbtn ${variant === "nav" ? "nav-icon" : ""}`}
      aria-label={LABEL[mode]}
      title={LABEL[mode]}
    >
      <Icon name={ICON[mode]} />
    </button>
  );
}
