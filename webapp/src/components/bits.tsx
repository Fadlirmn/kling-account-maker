import type { ReactNode } from "react";

/** Chip filter: aktif = violet, lainnya outlined. */
export function FilterChip({ active, onClick, disabled, children }: { active: boolean; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`pill ${active ? "pill-violet" : "pill-outlined"} disabled:opacity-60 disabled:cursor-wait`}
      aria-pressed={active}
    >
      {children}
    </button>
  );
}
