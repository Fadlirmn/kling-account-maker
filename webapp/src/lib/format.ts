// Format angka gaya ID: RB (ribu), JT (juta), M (miliar).
export function idShort(n: number | null | undefined): string {
  if (n == null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return trim(n / 1_000_000_000) + "M";
  if (abs >= 1_000_000) return trim(n / 1_000_000) + "JT";
  if (abs >= 1_000) return trim(n / 1_000) + "RB";
  return String(n);
}

function trim(v: number): string {
  return v.toFixed(1).replace(/\.0$/, "").replace(".", ",");
}

// angka penuh dengan pemisah ribuan titik (untuk tooltip)
export function idFull(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("id-ID");
}
