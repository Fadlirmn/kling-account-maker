"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "./ui";

/** Native <dialog> ber-gaya .dialog (surface-high, r16, backdrop blur). */
export function Dialog({
  open,
  onClose,
  title,
  size = "md",
  children,
  actions,
  /** body berisi blok (bukan teks) → tanpa pre-wrap */
  block,
  className = "",
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  size?: "md" | "lg";
  children?: ReactNode;
  actions?: ReactNode;
  block?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`dialog ${size === "lg" ? "lg" : ""} ${className}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <div className="dialog-inner">
          {title && <h2 className="dialog-title">{title}</h2>}
          {children && <div className={`dialog-body ${block ? "block" : ""}`}>{children}</div>}
          {actions && <div className="dialog-actions">{actions}</div>}
        </div>
      )}
    </dialog>
  );
}

/* ===== Confirm (Promise) ===== */
export type ConfirmOptions = {
  title: ReactNode;
  body?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;
const ConfirmCtx = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ opts: ConfirmOptions; resolve: (v: boolean) => void } | null>(null);

  const confirm = useCallback<ConfirmFn>((opts) => new Promise((resolve) => setState({ opts, resolve })), []);

  const done = (v: boolean) => {
    state?.resolve(v);
    setState(null);
  };

  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Dialog
        open={state !== null}
        onClose={() => done(false)}
        title={state?.opts.title}
        actions={
          <>
            <Button variant="text" onClick={() => done(false)}>
              {state?.opts.cancelLabel ?? "Batal"}
            </Button>
            <Button variant={state?.opts.danger ? "danger" : "primary"} onClick={() => done(true)}>
              {state?.opts.confirmLabel ?? "Lanjutkan"}
            </Button>
          </>
        }
      >
        {state?.opts.body}
      </Dialog>
    </ConfirmCtx.Provider>
  );
}

/** Pengganti window.confirm: `if (!(await confirm({ title, body }))) return;` */
export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmCtx);
  return (
    ctx ??
    (async (opts) => {
      const text = [typeof opts.title === "string" ? opts.title : "", typeof opts.body === "string" ? opts.body : ""].filter(Boolean).join("\n\n");
      return window.confirm(text || "Lanjutkan?");
    })
  );
}
