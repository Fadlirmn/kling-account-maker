"use client";

import { useEffect, useState } from "react";

/**
 * Baca CSS variable tema (--primary, --text3, …) sebagai warna terselesaikan — untuk library yang
 * butuh hex literal (recharts). Ikut berubah saat data-theme di <html> berganti (toggle terang/gelap).
 * Mengembalikan null sebelum mount (SSR) supaya pemanggil bisa menunda render.
 */
export function useThemeColors<T extends string>(names: readonly T[]): Record<T, string> | null {
  const [colors, setColors] = useState<Record<T, string> | null>(null);
  const key = names.join("|");

  useEffect(() => {
    const read = () => {
      const cs = getComputedStyle(document.documentElement);
      const out = {} as Record<T, string>;
      for (const n of names) out[n] = cs.getPropertyValue(`--${n}`).trim();
      setColors(out);
    };
    read();
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return colors;
}
