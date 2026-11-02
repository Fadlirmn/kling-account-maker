import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./Icon";

/* ===== Tone (status) ===== */
export type Tone = "success" | "warn" | "err" | "info" | "violet" | "neutral";

const dotTone: Record<Tone, string> = {
  success: "text-success",
  warn: "text-warn",
  err: "text-err",
  info: "text-info",
  violet: "text-secondary",
  neutral: "text-text3",
};

export function StatusDot({ tone = "neutral", pulse, className = "" }: { tone?: Tone; pulse?: boolean; className?: string }) {
  return <span className={`dot ${pulse ? "ping" : ""} ${dotTone[tone]} ${className}`} />;
}

/* ===== Pill / chip ===== */
const pillTone: Record<Tone, string> = {
  success: "pill-success",
  warn: "pill-warn",
  err: "pill-err",
  info: "pill-info",
  violet: "pill-violet",
  neutral: "",
};

export function Pill({
  tone = "neutral",
  pulse,
  dot,
  sm,
  icon,
  className = "",
  title,
  children,
}: {
  tone?: Tone;
  pulse?: boolean;
  /** tampilkan titik status (default: ikut `pulse`) */
  dot?: boolean;
  sm?: boolean;
  icon?: string;
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  const showDot = dot ?? pulse ?? false;
  return (
    <span className={`pill ${pillTone[tone]} ${sm ? "sm" : ""} ${className}`} title={title}>
      {showDot && <span className={`dot ${pulse ? "ping" : ""}`} />}
      {icon && <Icon name={icon} />}
      {children}
    </span>
  );
}

/* ===== Card ===== */
export function Card({
  children,
  className = "",
  title,
  desc,
  actions,
  padSm,
  pad0,
}: {
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
  desc?: ReactNode;
  actions?: ReactNode;
  padSm?: boolean;
  pad0?: boolean;
}) {
  return (
    <section className={`card ${padSm ? "pad-sm" : ""} ${pad0 ? "pad-0" : ""} ${className}`}>
      {(title || desc || actions) && (
        <div className="card-head">
          <div className="col">
            {title && <h2 className="card-title">{title}</h2>}
            {desc && <p className="card-desc">{desc}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

/** Placeholder saat data belum datang. */
export function Loading({ text = "Memuat…", className = "" }: { text?: string; className?: string }) {
  return (
    <Card className={`flex items-center justify-center gap-2 text-text2 body2 ${className}`}>
      <Icon name="progress_activity" spin className="text-secondary" />
      {text}
    </Card>
  );
}

/* ===== Button ===== */
type ButtonVariant = "primary" | "outlined" | "text" | "danger" | "danger-text";
type ButtonBase = {
  variant?: ButtonVariant;
  size?: "md" | "sm" | "lg";
  full?: boolean;
  /** state terpilih (segmented) — hanya untuk outlined */
  selected?: boolean;
  icon?: string;
  /** putar ikon (loading) */
  spin?: boolean;
  className?: string;
  title?: string;
  children?: ReactNode;
};
type ButtonProps = ButtonBase & {
  href?: string;
  target?: string;
  rel?: string;
  download?: boolean | string;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
};

const variantCls: Record<ButtonVariant, string> = {
  primary: "primary",
  outlined: "outlined",
  text: "text",
  danger: "danger",
  "danger-text": "danger text",
};

export function Button({
  variant = "outlined",
  size = "md",
  full,
  selected,
  icon,
  spin,
  className = "",
  title,
  children,
  href,
  target,
  rel,
  download,
  onClick,
  type = "button",
  disabled,
}: ButtonProps) {
  const cls = [
    "btn",
    variantCls[variant],
    size === "sm" ? "sm" : size === "lg" ? "lg" : "",
    full ? "full" : "",
    selected ? "selected" : "",
    disabled ? "disabled" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  const inner = (
    <>
      {icon && <Icon name={icon} spin={spin} />}
      {children}
    </>
  );
  if (href && !disabled)
    return (
      <Link href={href} className={cls} target={target} rel={rel} title={title} download={download}>
        {inner}
      </Link>
    );
  return (
    <button type={type} onClick={onClick} className={cls} disabled={disabled} title={title} aria-disabled={disabled}>
      {inner}
    </button>
  );
}

export function IconButton({
  name,
  label,
  onClick,
  href,
  sm,
  xs,
  primary,
  nav,
  spin,
  disabled,
  className = "",
  type = "button",
}: {
  name: string;
  /** aria-label + title (wajib: tombol tanpa teks) */
  label: string;
  onClick?: () => void;
  href?: string;
  sm?: boolean;
  xs?: boolean;
  primary?: boolean;
  nav?: boolean;
  spin?: boolean;
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  const cls = ["iconbtn", sm ? "sm" : "", xs ? "xs" : "", primary ? "primary" : "", nav ? "nav-icon" : "", className]
    .filter(Boolean)
    .join(" ");
  if (href)
    return (
      <Link href={href} className={cls} aria-label={label} title={label}>
        <Icon name={name} spin={spin} />
      </Link>
    );
  return (
    <button type={type} onClick={onClick} className={cls} aria-label={label} title={label} disabled={disabled}>
      <Icon name={name} spin={spin} />
    </button>
  );
}

/* ===== Delta ===== */
export function Delta({ value, suffix = "%" }: { value: number; suffix?: string }) {
  if (value === 0) return <span className="caption text-text3 tnum">= 0</span>;
  const up = value > 0;
  return (
    <span className={`caption font-semibold tnum inline-flex items-center gap-0.5 ${up ? "text-success" : "text-text3"}`}>
      <Icon name={up ? "arrow_drop_up" : "arrow_drop_down"} size="sm" />
      {Math.abs(value)}
      {suffix}
    </span>
  );
}

/* ===== PageBar: baris meta + aksi di atas konten (judul halaman ada di Topbar) ===== */
export function PageBar({ meta, right, children }: { meta?: ReactNode; right?: ReactNode; children?: ReactNode }) {
  if (!meta && !right && !children) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 -mb-1">
      <div className="caption text-text2 min-w-0">{meta ?? children}</div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

/* ===== Metric (KPI) ===== */
export function Metric({
  label,
  value,
  unit,
  sub,
  pill,
  className = "",
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  sub?: ReactNode;
  pill?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`metric ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="lbl">{label}</span>
        {pill}
      </div>
      <div className="val" title={typeof value === "string" ? value : undefined}>
        {value}
        {unit && <span className="caption text-text2 font-normal ml-1">{unit}</span>}
      </div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Metrics({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`metrics ${className}`}>{children}</div>;
}

/* ===== Avatar inisial ===== */
export function Avatar({ name, big, className = "" }: { name: string; big?: boolean; className?: string }) {
  const initials = name
    .replace(/^@/, "")
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? "")
    .join("") || "?";
  return (
    <span className={`avatar ${big ? "big" : ""} ${className}`} aria-hidden="true">
      {initials}
    </span>
  );
}

/* ===== Table wrapper ===== */
export function TableWrap({
  children,
  className = "",
  minWidth,
  scrollY,
}: {
  children: ReactNode;
  className?: string;
  /** lebar minimum tabel supaya kolom tidak terjepit (scroll horizontal) */
  minWidth?: number;
  scrollY?: boolean;
}) {
  return (
    <div className={`table-wrap ${scrollY ? "scroll-y" : ""} ${className}`}>
      <div style={minWidth ? { minWidth } : undefined}>{children}</div>
    </div>
  );
}

/* ===== Progress ===== */
export function Progress({ pct, className = "" }: { pct: number; className?: string }) {
  return (
    <div className={`progress ${className}`} role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
    </div>
  );
}

/* ===== Key/value row ===== */
export function KV({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="kv">
      <span>{k}</span>
      <span className="text-text min-w-0 break-words">{v}</span>
    </div>
  );
}
