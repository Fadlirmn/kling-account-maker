"""
Query/insert layer di atas models.py. Semua fungsi menerima SQLAlchemy Engine,
tanpa side effect lain (tidak buka browser, tidak fetch).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from models import (
    DEFAULT_SETTINGS, banned_domains as banned_t, kling_accounts as acc_t, runs as runs_t,
    settings as settings_t, users as users_t,
)

# settings yang bukan konfigurasi pembuatan akun → tidak menaikkan config_version
_NO_BUMP_KEYS = ("enable_scheduler", "schedule_time", "schedule_jitter_minutes",
                 "refill_interval_minutes", "standby_target", "debug_screenshots", "retention_days")

OK_STATUSES = ("success", "partial")
RUN_TRIGGERS = ("manual", "scheduled", "auto_refill")
ACCOUNT_STATUSES = ("pending", "standby", "active", "exhausted", "used", "banned", "failed")
# 3 tag pemakaian di dashboard → kelompok status
USAGE_GROUPS = {
    "unused": ("pending", "standby", "active"),      # belum dipakai
    "used": ("used",),                                # sudah dipakai
    "unusable": ("exhausted", "banned", "failed"),    # tidak bisa dipakai
}
LIVE_STATUSES = ("standby", "active")          # dihitung sebagai "sukses" untuk batas harian
TZ = ZoneInfo("Asia/Jakarta")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(r) -> dict:
    return dict(r._mapping)


def _aware(ts: datetime | None) -> datetime | None:
    """SQLite mengembalikan datetime naive — anggap UTC supaya bisa dibandingkan."""
    if ts is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _aware_row(d: dict) -> dict:
    for k in ("created_at", "updated_at", "started_at", "finished_at"):
        if k in d:
            d[k] = _aware(d[k])
    return d


# ── Settings ─────────────────────────────────────────────────────────────────
def get_settings(engine: Engine) -> dict:
    out = dict(DEFAULT_SETTINGS)
    with engine.connect() as con:
        for k, v in con.execute(select(settings_t.c.key, settings_t.c.value)):
            out[k] = v
    return out


def save_settings(engine: Engine, patch: dict) -> dict:
    cur = get_settings(engine)
    changed = {k: v for k, v in patch.items() if k in DEFAULT_SETTINGS and k != "config_version" and cur.get(k) != v}
    bump = any(k not in _NO_BUMP_KEYS for k in changed)
    if bump:
        changed["config_version"] = int(cur.get("config_version", 1)) + 1
    with engine.begin() as con:
        for k, v in changed.items():
            existing = con.execute(select(settings_t.c.key).where(settings_t.c.key == k)).first()
            if existing:
                con.execute(update(settings_t).where(settings_t.c.key == k).values(value=v, updated_at=_now()))
            else:
                con.execute(insert(settings_t).values(key=k, value=v, updated_at=_now()))
    return get_settings(engine)


def effective_settings(engine: Engine) -> dict:
    """Settings + clamp nilai agar runner aman meski DB berisi angka aneh."""
    s = get_settings(engine)
    s["workers"] = max(1, int(s.get("workers") or 1))
    s["batch_size"] = max(1, int(s.get("batch_size") or 1))
    s["max_attempts_per_slot"] = max(1, int(s.get("max_attempts_per_slot") or 1))
    s["browser_concurrency"] = max(1, int(s.get("browser_concurrency") or 1))
    s["max_daily_success"] = max(1, int(s.get("max_daily_success") or 1))
    s["delay_between_accounts"] = max(0, int(s.get("delay_between_accounts") or 0))
    s["standby_target"] = max(0, int(s.get("standby_target") or 0))
    return s


# ── Users ────────────────────────────────────────────────────────────────────
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(dk)}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        want = base64.b64decode(dk)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                             n=int(n), r=int(r), p=int(p), dklen=len(want))
        return hmac.compare_digest(got, want)
    except (ValueError, TypeError):
        return False


_USER_PUBLIC = (users_t.c.id, users_t.c.username, users_t.c.created_at, users_t.c.updated_at)


def list_users(engine: Engine) -> list[dict]:
    with engine.connect() as con:
        return [_row(r) for r in con.execute(select(*_USER_PUBLIC).order_by(users_t.c.username))]


def get_user(engine: Engine, user_id: int) -> dict | None:
    with engine.connect() as con:
        r = con.execute(select(*_USER_PUBLIC).where(users_t.c.id == user_id)).first()
    return _row(r) if r else None


def user_exists(engine: Engine, username: str) -> bool:
    with engine.connect() as con:
        return con.execute(select(users_t.c.id).where(users_t.c.username == username)).first() is not None


def create_user(engine: Engine, username: str, password: str) -> dict:
    now = _now()
    with engine.begin() as con:
        uid = con.execute(insert(users_t).values(
            username=username, password_hash=hash_password(password), created_at=now, updated_at=now,
        )).inserted_primary_key[0]
    return get_user(engine, uid)


def set_password(engine: Engine, user_id: int, password: str) -> bool:
    with engine.begin() as con:
        res = con.execute(update(users_t).where(users_t.c.id == user_id)
                          .values(password_hash=hash_password(password), updated_at=_now()))
    return res.rowcount > 0


def delete_user(engine: Engine, user_id: int) -> bool:
    with engine.begin() as con:
        return con.execute(delete(users_t).where(users_t.c.id == user_id)).rowcount > 0


def verify_user(engine: Engine, username: str, password: str) -> bool:
    with engine.connect() as con:
        r = con.execute(select(users_t.c.password_hash).where(users_t.c.username == username)).first()
    if r is None:
        hash_password(password)  # samakan waktu respons user ada/tidak ada
        return False
    return check_password(password, r[0])


# ── Run lifecycle ────────────────────────────────────────────────────────────
# kolom log bisa besar (satu baris per akun + traceback), jadi tidak ikut di daftar
# yang dipoll tiap 10 detik — ambil lewat get_run/run_log
_RUN_COLS = [c for c in runs_t.c if c.name != "log"]


def mark_stale_running_as_failed(engine: Engine) -> int:
    """Run yang masih 'running' saat backend baru start pasti orphan — _RUNNING itu
    in-memory (threading.Event), reset tiap restart container. Dipanggil sekali di
    lifespan() startup, sebelum scheduler/request manapun jalan."""
    with engine.begin() as con:
        res = con.execute(
            update(runs_t).where(runs_t.c.status == "running")
            .values(status="failed", finished_at=_now(),
                    error_message="Run terputus: proses backend restart/rebuild sebelum run selesai")
        )
        return res.rowcount


def create_run(engine: Engine, trigger: str, requested: int, workers: int,
               provider: str | None, config_version: int) -> int:
    with engine.begin() as con:
        res = con.execute(insert(runs_t).values(
            trigger=trigger, requested=int(requested), workers=int(workers), provider=provider,
            config_version=int(config_version), status="running", started_at=_now(),
        ))
        return int(res.inserted_primary_key[0])


def finish_run(engine: Engine, run_id: int, status: str, created_ok: int = 0, failed: int = 0,
               skipped: int = 0, error_message: str | None = None, log: str | None = None) -> None:
    vals: dict[str, Any] = dict(status=status, finished_at=_now(), created_ok=int(created_ok),
                                failed=int(failed), skipped=int(skipped), error_message=error_message, log=log)
    with engine.begin() as con:
        con.execute(update(runs_t).where(runs_t.c.id == run_id).values(**vals))


def get_run(engine: Engine, run_id: int, with_log: bool = True) -> dict | None:
    cols = [runs_t] if with_log else _RUN_COLS
    with engine.connect() as con:
        r = con.execute(select(*cols).where(runs_t.c.id == run_id)).first()
    return _aware_row(_row(r)) if r else None


def list_runs(engine: Engine, limit: int = 50) -> list[dict]:
    with engine.connect() as con:
        rows = con.execute(select(*_RUN_COLS).order_by(runs_t.c.id.desc()).limit(limit)).all()
    return [_aware_row(_row(r)) for r in rows]


def latest_run(engine: Engine, status_in: Iterable[str] | None = None) -> dict | None:
    q = select(*_RUN_COLS)
    if status_in:
        q = q.where(runs_t.c.status.in_(tuple(status_in)))
    with engine.connect() as con:
        r = con.execute(q.order_by(runs_t.c.id.desc()).limit(1)).first()
    return _aware_row(_row(r)) if r else None


def purge_old_runs(engine: Engine, days: int) -> list[int]:
    """Hapus run lebih tua dari n hari (akun tetap; run_id → NULL via FK)."""
    cutoff = _now() - timedelta(days=int(days))
    with engine.begin() as con:
        ids = [r[0] for r in con.execute(select(runs_t.c.id).where(runs_t.c.started_at < cutoff))]
        if ids:
            con.execute(update(acc_t).where(acc_t.c.run_id.in_(ids)).values(run_id=None))
            con.execute(delete(runs_t).where(runs_t.c.id.in_(ids)))
    return ids


# ── Accounts ─────────────────────────────────────────────────────────────────
_ACC_UPSERT_COLS = ("password", "user_id", "otp", "cookies", "proxy", "email_mode", "status",
                    "attempts", "credits", "plan", "error", "run_id")
_ACC_LITE = [c for c in acc_t.c if c.name not in ("cookies", "otp", "proxy")]   # password ikut: dashboard menampilkannya


def upsert_account(engine: Engine, data: dict, run_id: int | None = None) -> None:
    """INSERT atau UPDATE berdasarkan email. cookies list → JSON string."""
    email = str(data.get("email", "")).strip().lower()
    if not email:
        raise ValueError("upsert_account: email kosong")
    cookies = data.get("cookies", "")
    if isinstance(cookies, (list, dict)):
        cookies = json.dumps(cookies)
    now = _now()
    vals = dict(
        email=email,
        password=str(data.get("password") or ""),
        user_id=str(data.get("user_id") or ""),
        otp=str(data.get("otp") or ""),
        cookies=cookies or "",
        proxy=str(data.get("proxy") or ""),
        email_mode=str(data.get("email_mode") or ""),
        status=str(data.get("status") or "pending"),
        attempts=int(data.get("attempts") or 0),
        credits=str(data.get("credits") or (data.get("extra") or {}).get("credits", "") or ""),
        plan=str(data.get("plan") or (data.get("extra") or {}).get("plan", "") or ""),
        error=(data.get("error") or None),
        run_id=run_id,
        created_at=now, updated_at=now,
    )
    upd = {k: vals[k] for k in _ACC_UPSERT_COLS}
    upd["updated_at"] = now
    ins = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = ins(acc_t).values(**vals).on_conflict_do_update(index_elements=["email"], set_=upd)
    with engine.begin() as con:
        con.execute(stmt)


def _acc_lite_row(r) -> dict:
    d = _aware_row(_row(r))
    return d


def list_accounts(engine: Engine, status: str | None = None, q: str | None = None,
                  page: int = 1, size: int = 50, sort: str = "created_desc",
                  usage: str | None = None) -> dict:
    page, size = max(1, int(page)), max(1, min(500, int(size)))
    cond = []
    if status:
        cond.append(acc_t.c.status == status)
    if usage:
        cond.append(acc_t.c.status.in_(USAGE_GROUPS[usage]))
    if q:
        like = f"%{q.strip().lower()}%"
        cond.append(or_(func.lower(acc_t.c.email).like(like), func.lower(acc_t.c.user_id).like(like)))
    order = acc_t.c.created_at.asc() if sort == "created_asc" else acc_t.c.created_at.desc()
    has_cookies = (func.length(func.coalesce(acc_t.c.cookies, "")) > 2).label("has_cookies")
    with engine.connect() as con:
        total = con.execute(select(func.count()).select_from(acc_t).where(*cond)).scalar() or 0
        rows = con.execute(
            select(*_ACC_LITE, has_cookies).where(*cond).order_by(order, acc_t.c.id.desc())
            .offset((page - 1) * size).limit(size)
        ).all()
    items = [_acc_lite_row(r) for r in rows]
    for it in items:
        it["has_cookies"] = bool(it.get("has_cookies"))
    return {"items": items, "total": int(total), "page": page, "size": size, "counts": account_counts(engine)}


def get_account(engine: Engine, account_id: int) -> dict | None:
    with engine.connect() as con:
        r = con.execute(select(acc_t).where(acc_t.c.id == account_id)).first()
    if not r:
        return None
    d = _aware_row(_row(r))
    d["has_cookies"] = len(d.get("cookies") or "") > 2
    return d


def set_account_status(engine: Engine, account_id: int, status: str) -> bool:
    if status not in ACCOUNT_STATUSES:
        raise ValueError(f"status tidak valid: {status}")
    with engine.begin() as con:
        return con.execute(update(acc_t).where(acc_t.c.id == account_id)
                           .values(status=status, updated_at=_now())).rowcount > 0


def bulk_set_status(engine: Engine, ids: list[int], status: str) -> int:
    """Ubah status banyak akun sekaligus (tandai dipakai/belum dipakai). Return jumlah baris."""
    if status not in ACCOUNT_STATUSES:
        raise ValueError(f"status tidak valid: {status}")
    if not ids:
        return 0
    with engine.begin() as con:
        return con.execute(update(acc_t).where(acc_t.c.id.in_(ids)).values(status=status, updated_at=_now())).rowcount


def delete_accounts(engine: Engine, ids: list[int]) -> int:
    if not ids:
        return 0
    with engine.begin() as con:
        return con.execute(delete(acc_t).where(acc_t.c.id.in_(ids))).rowcount


def account_counts(engine: Engine) -> dict[str, int]:
    out = {s: 0 for s in ACCOUNT_STATUSES}
    with engine.connect() as con:
        for st, n in con.execute(select(acc_t.c.status, func.count()).group_by(acc_t.c.status)):
            out[st] = int(n)
    return out


def count_by_status(engine: Engine, status: str) -> int:
    with engine.connect() as con:
        return int(con.execute(select(func.count()).select_from(acc_t).where(acc_t.c.status == status)).scalar() or 0)


def _count_since(engine: Engine, since: datetime, statuses: Iterable[str]) -> int:
    with engine.connect() as con:
        return int(con.execute(
            select(func.count()).select_from(acc_t)
            .where(acc_t.c.status.in_(tuple(statuses)), acc_t.c.created_at >= since)
        ).scalar() or 0)


def count_success_last_24h(engine: Engine) -> int:
    return _count_since(engine, _now() - timedelta(hours=24), LIVE_STATUSES)


def count_failed_last_24h(engine: Engine) -> int:
    return _count_since(engine, _now() - timedelta(hours=24), ("failed",))


def created_per_day(engine: Engine, days: int = 14) -> list[dict]:
    """[{day:'YYYY-MM-DD', created:n, failed:m}] untuk n hari terakhir (WIB), zero-filled."""
    days = max(1, int(days))
    today = datetime.now(TZ).date()
    start_day = today - timedelta(days=days - 1)
    since = datetime.combine(start_day, datetime.min.time(), tzinfo=TZ).astimezone(timezone.utc)
    buckets = {(start_day + timedelta(days=i)).isoformat(): {"created": 0, "failed": 0} for i in range(days)}
    with engine.connect() as con:
        rows = con.execute(select(acc_t.c.created_at, acc_t.c.status).where(acc_t.c.created_at >= since)).all()
    for ts, st in rows:
        ts = _aware(ts)
        if ts is None:
            continue
        key = ts.astimezone(TZ).date().isoformat()
        if key not in buckets:
            continue
        if st in LIVE_STATUSES or st in ("exhausted", "used"):
            buckets[key]["created"] += 1
        elif st == "failed":
            buckets[key]["failed"] += 1
    return [{"day": k, **v} for k, v in buckets.items()]


def export_rows(engine: Engine, status: str | None = None, ids: list[int] | None = None,
                usage: str | None = None) -> list[dict]:
    """Semua kolom kecuali cookies (→ has_cookies). Untuk xlsx/csv/json. ids = hanya akun terpilih."""
    cond = [acc_t.c.status == status] if status else []
    if usage:
        cond.append(acc_t.c.status.in_(USAGE_GROUPS[usage]))
    if ids:
        cond.append(acc_t.c.id.in_(ids))
    with engine.connect() as con:
        rows = con.execute(select(acc_t).where(*cond).order_by(acc_t.c.id)).all()
    out = []
    for r in rows:
        d = _aware_row(_row(r))
        d["has_cookies"] = len(d.pop("cookies") or "") > 2
        out.append(d)
    return out


def accounts_for_run(engine: Engine, run_id: int) -> list[dict]:
    with engine.connect() as con:
        rows = con.execute(select(*_ACC_LITE).where(acc_t.c.run_id == run_id).order_by(acc_t.c.id)).all()
    return [_acc_lite_row(r) for r in rows]


# ── Domains ──────────────────────────────────────────────────────────────────
def list_banned_domains(engine: Engine) -> list[str]:
    with engine.connect() as con:
        return [r[0].lower() for r in con.execute(select(banned_t.c.domain))]


def ban_domain(engine: Engine, domain: str) -> None:
    if not domain:
        return
    ins = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = ins(banned_t).values(domain=domain.lower(), created_at=_now()).on_conflict_do_nothing(index_elements=["domain"])
    with engine.begin() as con:
        con.execute(stmt)


# ── Summary ──────────────────────────────────────────────────────────────────
def summary(engine: Engine) -> dict:
    counts = account_counts(engine)
    today_start = datetime.combine(datetime.now(TZ).date(), datetime.min.time(), tzinfo=TZ).astimezone(timezone.utc)
    return {
        "last_run": latest_run(engine),
        "standby": counts.get("standby", 0),
        "active": counts.get("active", 0),
        "total": sum(counts.values()),
        "created_24h": count_success_last_24h(engine),
        "failed_24h": count_failed_last_24h(engine),
        "created_today": _count_since(engine, today_start, LIVE_STATUSES),
        "counts": counts,
    }
