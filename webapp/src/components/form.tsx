import type { ReactNode, SelectHTMLAttributes, InputHTMLAttributes } from "react";
import { Icon } from "./Icon";

/** Label + kontrol + hint. Pakai <input className="input"> / <Select> sebagai child. */
export function Field({
  label,
  hint,
  error,
  icon,
  className = "",
  children,
}: {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  /** ikon Material di kiri input */
  icon?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`field ${icon ? "icon-left" : ""} ${className}`}>
      {label && <span className="field-label">{label}</span>}
      <span className="wrap block">
        {icon && <Icon name={icon} className="icon" />}
        {children}
      </span>
      {error ? <span className="hint err">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </label>
  );
}

/** Kelas input standar (untuk <input>/<textarea> langsung). */
export const inputCls = "input";

export function Select({
  compact,
  className = "",
  wrapClassName = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { compact?: boolean; wrapClassName?: string }) {
  return (
    <span className={`select-wrap block ${wrapClassName}`}>
      <select className={`input ${compact ? "compact" : ""} ${className}`} {...rest}>
        {children}
      </select>
    </span>
  );
}

/** Switch (daisyUI pattern) dengan label + deskripsi. */
export function Switch({
  label,
  desc,
  sm,
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; desc?: ReactNode; sm?: boolean }) {
  return (
    <label className={`label ${className}`}>
      <input type="checkbox" className={`toggle ${sm ? "toggle-sm" : ""}`} {...rest} />
      <span className="label-text">
        <span>{label}</span>
        {desc && <span className="label-desc">{desc}</span>}
      </span>
    </label>
  );
}

export function Checkbox({
  label,
  desc,
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; desc?: ReactNode }) {
  return (
    <label className={`label ${className}`}>
      <input type="checkbox" className="checkbox" {...rest} />
      <span className="label-text">
        <span>{label}</span>
        {desc && <span className="label-desc">{desc}</span>}
      </span>
    </label>
  );
}

export function Fieldset({ legend, children, className = "" }: { legend: ReactNode; children: ReactNode; className?: string }) {
  return (
    <fieldset className={`fieldset ${className}`}>
      <legend className="fieldset-legend">{legend}</legend>
      {children}
    </fieldset>
  );
}
