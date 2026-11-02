import type { ReactNode } from "react";
import { Icon } from "./Icon";

export type AlertTone = "default" | "info" | "success" | "warn" | "err";

const ICON: Record<AlertTone, string> = {
  default: "info",
  info: "info",
  success: "check_circle",
  warn: "warning",
  err: "error",
};

/** Notifikasi inline (bukan toast) — sama seperti .alert di desain sumber. */
export function Alert({
  tone = "default",
  icon,
  title,
  children,
  actions,
  onClose,
  compact,
  className = "",
}: {
  tone?: AlertTone;
  icon?: string | null;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  onClose?: () => void;
  compact?: boolean;
  className?: string;
}) {
  const name = icon === null ? null : icon ?? ICON[tone];
  return (
    <div className={`alert ${tone === "default" ? "" : tone} ${compact ? "compact" : ""} ${className}`} role={tone === "err" ? "alert" : "status"}>
      {name && <Icon name={name} />}
      <div className="alert-body">
        {title && <span className="alert-title">{title}</span>}
        {children && <span>{children}</span>}
        {actions && <div className="alert-actions">{actions}</div>}
      </div>
      {onClose && (
        <button type="button" className="alert-close" onClick={onClose} aria-label="Tutup">
          <Icon name="close" size="md" />
        </button>
      )}
    </div>
  );
}

/** Pesan singkat hasil aksi (ok / gagal). */
export function FlashMsg({ msg, className = "" }: { msg: { ok: boolean; text: string } | null; className?: string }) {
  if (!msg) return null;
  return (
    <Alert tone={msg.ok ? "success" : "err"} compact className={className}>
      {msg.text}
    </Alert>
  );
}
