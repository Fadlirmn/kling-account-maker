#!/usr/bin/env python3
"""
CLI pembuat akun standby (satu run, tanpa API/dashboard).

  python account_creator.py --pre-create 10
  python account_creator.py --pre-create 50 --workers 3
  python account_creator.py --provider mailtm          # count/workers dari settings DB

Settings (workers, batch_size, provider, batas harian) dibaca dari tabel settings
(diisi dari dashboard); argumen CLI menimpanya untuk run ini saja.
"""

from __future__ import annotations

import argparse
import sys

import core.bootstrap  # noqa: F401  — env Firefox, patch Playwright, .env, MMDB (HARUS pertama)
from core import config
from core.log import err, ok, warn, colorize


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    p = argparse.ArgumentParser(description=f"{config.SITE_NAME} Standby Account Creator",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--pre-create", type=int, default=None, metavar="N", help="Jumlah akun (default: settings.batch_size)")
    p.add_argument("--workers", type=int, default=None,
                   help=f"Browser paralel (default: settings.workers; dibatasi RAM guard {config.RAM_PER_WORKER_MB}MB/worker)")
    p.add_argument("--provider", choices=["kurmamail", "webhook", "local_tempmail", "1secmail", "mailtm", "gptmail"],
                   help="Override provider email")
    args = p.parse_args()

    problems = config.validate(require_password=True)
    if problems:
        for pr in problems:
            err(pr)
        return 2

    import db
    import repo
    from models import init_db
    from core.runner import run_batch

    engine = db.get_engine()
    init_db(engine)
    run_id = run_batch(engine, "manual", count=args.pre_create, workers=args.workers,
                       provider=args.provider, log=lambda line: print(colorize(line), flush=True))
    r = repo.get_run(engine, run_id, with_log=False) or {}
    line = f"run #{run_id} {r.get('status')} — ok={r.get('created_ok', 0)} failed={r.get('failed', 0)} skipped={r.get('skipped', 0)}"
    (ok if r.get("created_ok") else warn)(line)
    if r.get("error_message"):
        warn(r["error_message"])
    return 0 if r.get("created_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
