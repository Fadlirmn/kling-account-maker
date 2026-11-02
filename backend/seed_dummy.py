#!/usr/bin/env python3
"""
Isi DB dengan data dummy supaya dashboard punya isi sebelum flow kling.ai jadi.

  python seed_dummy.py                 # tambah 14 hari run + akun (idempoten per email dummy)
  python seed_dummy.py --reset         # hapus semua akun dummy (@dummy.kling.test) & run dummy dulu
  python seed_dummy.py --days 30 --per-day 12

Juga user dashboard dummy (config.json seed.users) dengan password DASHBOARD_USER_DEFAULT_PASSWORD (.env).
Data: run harian (scheduled) + beberapa manual/auto_refill, status campur success/partial/failed,
log bergaya RunLogger; akun dengan status standby/active/exhausted/used/banned/failed,
email *@dummy.kling.test, cookies JSON palsu, proxy ter-mask. Tidak menyentuh akun asli.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, insert, text

import core.bootstrap  # noqa: F401
from core import config
import db
import repo
from models import init_db, kling_accounts as acc_t, runs as runs_t

DUMMY_DOMAIN = str(config.CONFIG.get("seed", {}).get("domain") or "dummy.kling.test")
PASSWORD = config.KLING_DEFAULT_PASSWORD or "Kling#Maker2026"   # satu password untuk semua akun & user dummy
DUMMY_USERS = list(config.CONFIG.get("seed", {}).get("users") or ["ops", "qa", "viewer"])   # dari config.json "seed.users"
# password user dashboard dummy: .env DASHBOARD_USER_DEFAULT_PASSWORD, fallback DASHBOARD_PASSWORD, fallback PASSWORD akun
USER_PASSWORD = os.getenv("DASHBOARD_USER_DEFAULT_PASSWORD", "").strip() or os.getenv("DASHBOARD_PASSWORD", "").strip() or PASSWORD
WIB = timezone(timedelta(hours=7))
PROVIDERS = ["webhook", "1secmail", "mailtm", "webhook", "webhook"]
FAIL_CODES = ["otp timeout", "PROXY_FLAGGED_CLOUDFLARE", "email input not found", "exception: NS_ERROR_NET_INTERRUPT",
              "DOMAIN_BLOCKED:mail.contoh.biz.id", "otp extract failed"]
STATUS_AFTER = ["standby"] * 6 + ["active"] * 3 + ["exhausted", "used", "banned"]


def _email(i: int) -> str:
    return f"kling_{random.randrange(10**9):09x}{i:03d}@{DUMMY_DOMAIN}"


def _log(run_id: int, trigger: str, start: datetime, n: int, workers: int, ok_emails: list[str],
         fail: list[tuple[str, str]], status: str, dur: float) -> str:
    t0 = start.astimezone(WIB)
    lines = [f"=== run #{run_id} trigger={trigger} start {t0:%Y-%m-%d %H:%M:%S} WIB ==="]
    el = 0.0

    def emit(level, msg, dt=0.0):
        nonlocal el
        el += dt
        lines.append(f"[{(t0 + timedelta(seconds=el)):%H:%M:%S}] [+{el:.1f}s] {level:<5} {msg}")

    emit("STAGE", "── persiapan ──")
    emit("INFO", f"site=kling | slot={n} | workers={workers} | provider=webhook | chain=['webhook', '1secmail', 'mailtm'] | attempts/slot=8")
    emit("INFO", "proxy: 12 list, 1 blacklist | domain: 6 aktif, 1 banned", 0.1)
    emit("STAGE", "── persiapan selesai (0.1s) ──")
    emit("STAGE", f"── pembuatan {n} akun × {workers} worker ──")
    done = 0
    for em in ok_emails:
        done += 1
        emit("INFO", f"[slot {done}] attempt 1/8 → {em} (webhook)", 1.2)
        emit("INFO", f"[{em.split('@')[0][:16]}] → buka halaman signup", 4.0)
        emit("INFO", f"[{em.split('@')[0][:16]}] ✓ OTP diterima, login terkonfirmasi", 30.0)
        emit("INFO", f"[{done}/{n}] STANDBY OK — {em} | user u{random.randrange(10**7)} | attempt 1", 2.0)
    for em, code in fail:
        done += 1
        emit("INFO", f"[slot {done}] attempt 1/8 → {em} (1secmail)", 1.0)
        emit("WARN", f"[slot {done}] gagal: {code} → retry dalam 5s", 25.0)
        emit("WARN", f"[{done}/{n}] GAGAL — {code} (attempt 8)", 60.0)
    emit("STAGE", f"── pembuatan {n} akun × {workers} worker selesai ({dur:.1f}s) ──")
    lines.append(f"=== run #{run_id} {status} in {dur:.1f}s (ok={len(ok_emails)} failed={len(fail)} skipped=0) ===")
    return "\n".join(lines)


def seed_users(engine) -> None:
    """User dashboard dummy, idempoten: dibuat kalau belum ada, password selalu disamakan dengan USER_PASSWORD."""
    admins = set(config.CONFIG.get("seed", {}).get("admins") or [])
    for u in DUMMY_USERS:
        role = "admin" if u in admins else "member"
        existing = next((x for x in repo.list_users(engine) if x["username"] == u), None)
        if existing:
            repo.set_password(engine, existing["id"], USER_PASSWORD)
            repo.set_role(engine, existing["id"], role)
        else:
            repo.create_user(engine, u, USER_PASSWORD, role)
    print(f"users: {len(DUMMY_USERS)} user ({DUMMY_USERS[0]} … {DUMMY_USERS[-1]}) password dari DASHBOARD_USER_DEFAULT_PASSWORD / DASHBOARD_PASSWORD")


LEGACY_DUMMY_USERS = {"ops", "qa", "viewer"}   # nama seed lama, ikut dibersihkan


def reset(engine) -> None:
    for x in repo.list_users(engine):
        if x["username"] in DUMMY_USERS or x["username"] in LEGACY_DUMMY_USERS:
            repo.delete_user(engine, x["id"])
    with engine.begin() as con:
        n_acc = con.execute(delete(acc_t).where(acc_t.c.email.like(f"%@{DUMMY_DOMAIN}"))).rowcount
        n_run = con.execute(delete(runs_t).where(runs_t.c.error_message.like("%[dummy]%")
                                                 | runs_t.c.log.like("%dummy.kling.test%"))).rowcount
    print(f"reset: {n_acc} akun dummy, {n_run} run dummy dihapus")


def seed(engine, days: int, per_day: int) -> None:
    now = datetime.now(timezone.utc)
    total_acc = total_run = 0
    for d in range(days, 0, -1):
        day = now - timedelta(days=d - 1)
        n_runs = 1 + (1 if d % 3 == 0 else 0)
        for k in range(n_runs):
            trigger = "scheduled" if k == 0 else random.choice(["manual", "auto_refill"])
            start = day.replace(hour=20 if k == 0 else random.randint(0, 15), minute=random.randint(0, 59), second=0, microsecond=0)
            n = per_day if k == 0 else random.randint(2, 6)
            workers = random.choice([2, 3])
            roll = random.random()
            if roll < 0.12:
                ok_n, status = 0, "failed"
            elif roll < 0.45:
                ok_n, status = max(1, n - random.randint(1, 3)), "partial"
            else:
                ok_n, status = n, "success"
            dur = ok_n * 38 + (n - ok_n) * 86 + 5
            with engine.begin() as con:
                rid = con.execute(insert(runs_t).values(
                    trigger=trigger, config_version=2, requested=n, workers=workers, provider=PROVIDERS[d % len(PROVIDERS)],
                    started_at=start, finished_at=start + timedelta(seconds=dur), status="running",
                )).inserted_primary_key[0]
            ok_emails = [_email(i) for i in range(ok_n)]
            fails = [(_email(100 + i), random.choice(FAIL_CODES)) for i in range(n - ok_n)]
            for i, em in enumerate(ok_emails):
                st = random.choice(STATUS_AFTER) if d > 2 else "standby"
                repo.upsert_account(engine, {
                    "email": em, "password": PASSWORD, "user_id": f"u{random.randrange(10**8)}",
                    "otp": f"{random.randrange(10**6):06d}",
                    "cookies": [{"name": "kling_session", "value": f"dummy-{random.randrange(10**12):x}", "domain": ".klingai.com", "path": "/"}],
                    "proxy": "http://[REDACTED]:[REDACTED]@proxy.example.net:2312", "email_mode": "webhook",
                    "status": st, "attempts": 1 + (i % 2), "credits": str(random.choice([66, 100, 166, 0])) if st != "pending" else "",
                    "plan": "free",
                }, rid)
                with engine.begin() as con:
                    ts = start + timedelta(seconds=40 * (i + 1))
                    con.execute(text("UPDATE kling_accounts SET created_at=:t, updated_at=:t WHERE email=:e"), {"t": ts, "e": em})
            for i, (em, code) in enumerate(fails):
                repo.upsert_account(engine, {"email": em, "password": PASSWORD, "email_mode": "1secmail",
                                             "status": "failed", "attempts": 8, "error": code}, rid)
                with engine.begin() as con:
                    ts = start + timedelta(seconds=40 * ok_n + 90 * (i + 1))
                    con.execute(text("UPDATE kling_accounts SET created_at=:t, updated_at=:t WHERE email=:e"), {"t": ts, "e": em})
            err = None
            if fails:
                codes: dict[str, int] = {}
                for _, c in fails:
                    codes[c.split(":", 1)[0]] = codes.get(c.split(":", 1)[0], 0) + 1
                err = f"{len(fails)} slot gagal: " + "; ".join(f"{v}×{k}" for k, v in codes.items()) + " [dummy]"
            repo.finish_run(engine, rid, status, ok_n, len(fails), 0, err,
                            _log(rid, trigger, start, n, workers, ok_emails, fails, status, dur))
            with engine.begin() as con:
                con.execute(text("UPDATE runs SET finished_at=:f WHERE id=:i"), {"f": start + timedelta(seconds=dur), "i": rid})
            total_run += 1
            total_acc += n
    repo.ban_domain(engine, "mail.contoh.biz.id")
    repo.save_settings(engine, {"standby_target": 40, "batch_size": per_day})
    print(f"seed: {total_run} run, {total_acc} akun dummy (@{DUMMY_DOMAIN}) selama {days} hari")
    print("counts:", repo.account_counts(engine))


def main() -> int:
    p = argparse.ArgumentParser(description="Seed data dummy Kling Account Maker")
    seed_cfg = config.CONFIG.get("seed", {})
    p.add_argument("--days", type=int, default=int(seed_cfg.get("days", 14)))
    p.add_argument("--per-day", type=int, default=int(seed_cfg.get("per_day", 10)))
    p.add_argument("--reset", action="store_true", help="hapus data dummy lama dulu")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    random.seed(a.seed)
    engine = db.get_engine()
    init_db(engine)
    if a.reset:
        reset(engine)
    seed(engine, a.days, a.per_day)
    seed_users(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
