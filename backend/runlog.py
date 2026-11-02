"""
Logger per run pembuatan akun: baris berlevel + durasi, dikelompokkan per tahap.

Format baris: "[HH:MM:SS] [+12.3s] LEVEL  pesan" (jam WIB, durasi sejak run mulai).
Semua baris ditampung di .lines (dipakai repo.finish_run → kolom runs.log)
dan, kalau LOG_DIR bisa ditulis, juga disalin ke file sendiri per run.

Thread-safe: worker ThreadPool (satu per akun) memanggil emit bersamaan → _raw dikunci.
child(prefix) memberi logger kecil ber-prefix untuk dipass ke flow site
(interface ok/err/info/warn/step seperti core.log.Logger).
"""

from __future__ import annotations

import os
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from typing import Callable

WIB = timezone(timedelta(hours=7))
LOG_DIR = os.getenv("LOG_DIR", "/data/logs")


def describe_exc(e: BaseException) -> str:
    """Ringkas exception jadi satu baris; error SQLAlchemy tanpa dump bound parameter."""
    orig = getattr(e, "orig", None)  # SQLAlchemy → error driver asli (psycopg dll)
    first = str(orig or e).strip().splitlines()
    msg = first[0][:300] if first else ""
    out = f"{type(e).__name__}: {msg}"
    stmt = getattr(e, "statement", None)
    if stmt:
        out += f" | sql={' '.join(str(stmt).split())[:160]}"
    params = getattr(e, "params", None)
    if isinstance(params, (list, tuple)):
        out += f" | rows={len(params)}"
    return out


def format_tb(e: BaseException, max_line: int = 500) -> str:
    """Traceback lengkap (semua frame), tiap baris dipotong supaya dump bound
    parameter SQLAlchemy tidak membanjiri log."""
    out = []
    for line in "".join(traceback.format_exception(type(e), e, e.__traceback__)).rstrip().splitlines():
        out.append(line if len(line) <= max_line else line[:max_line] + " …[dipotong]")
    return "\n".join(out)


class RunLogger:
    """Kumpulkan baris log satu run; tulis juga ke stdout (log) dan file per run."""

    def __init__(self, run_id: int, trigger: str, log: Callable[[str], None] = print,
                 log_dir: str | None = None):
        self.run_id = run_id
        self.trigger = trigger
        self._log = log
        self.lines: list[str] = []
        self._t0 = monotonic()
        self._lock = threading.Lock()
        self._fh = self._open_file(log_dir if log_dir is not None else LOG_DIR)
        self._raw(f"=== run #{run_id} trigger={trigger} start {datetime.now(WIB):%Y-%m-%d %H:%M:%S} WIB ===")

    # ── output ──────────────────────────────────────────────────────────────
    def _open_file(self, log_dir: str):
        try:
            d = Path(log_dir)
            d.mkdir(parents=True, exist_ok=True)
            return open(d / f"run_{self.run_id}.log", "a", encoding="utf-8")
        except Exception:  # noqa: BLE001 — log file opsional, jangan jatuhkan run
            return None

    def _raw(self, line: str) -> None:
        with self._lock:
            self.lines.append(line)
            try:
                self._log(line)
            except Exception:  # noqa: BLE001
                pass
            if self._fh is not None:
                try:
                    self._fh.write(line + "\n")
                    self._fh.flush()
                except Exception:  # noqa: BLE001
                    self._fh = None

    def emit(self, level: str, msg: str) -> None:
        self._raw(f"[{datetime.now(WIB):%H:%M:%S}] [+{monotonic() - self._t0:.1f}s] {level:<5} {msg}")

    # ── level ───────────────────────────────────────────────────────────────
    def info(self, msg: str) -> None:
        self.emit("INFO", msg)

    def warn(self, msg: str) -> None:
        self.emit("WARN", msg)

    def error(self, msg: str, exc: BaseException | None = None) -> None:
        self.emit("ERROR", f"{msg} — {describe_exc(exc)}" if exc is not None else msg)
        if exc is not None:
            self._raw(format_tb(exc))

    @contextmanager
    def stage(self, name: str):
        """Blok tahap: tandai mulai/selesai + durasi tahap sendiri."""
        self.emit("STAGE", f"── {name} ──")
        t = monotonic()
        try:
            yield self
        except BaseException:
            self.emit("STAGE", f"── {name} gagal setelah {monotonic() - t:.1f}s ──")
            raise
        else:
            self.emit("STAGE", f"── {name} selesai ({monotonic() - t:.1f}s) ──")

    def child(self, prefix: str) -> "SlotLog":
        return SlotLog(self, prefix)

    def finish(self, status: str, **counts: int) -> None:
        extra = " ".join(f"{k}={v}" for k, v in counts.items())
        self._raw(f"=== run #{self.run_id} {status} in {monotonic() - self._t0:.1f}s ({extra}) ===")
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except Exception:  # noqa: BLE001
                    pass
                self._fh = None


class SlotLog:
    """Logger ber-prefix untuk satu slot/akun; interface sama dengan core.log.Logger."""

    def __init__(self, rl: RunLogger, prefix: str):
        self._rl = rl
        self.prefix = f"[{prefix}] " if prefix else ""

    def info(self, m) -> None: self._rl.info(self.prefix + str(m))
    def ok(self, m) -> None:   self._rl.info(self.prefix + "✓ " + str(m))
    def step(self, m) -> None: self._rl.info(self.prefix + "→ " + str(m))
    def warn(self, m) -> None: self._rl.warn(self.prefix + str(m))
    def err(self, m) -> None:  self._rl.error(self.prefix + str(m))
