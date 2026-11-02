"""
REST API (FastAPI) + APScheduler untuk dashboard Kling Account Maker.

  uvicorn api:app --host 0.0.0.0 --port 8000

Satu run (batch pembuatan akun) berjalan pada satu waktu — dijaga _RUNNING + _claim_running().
Batch dipicu scheduler (harian / isi ulang) atau CLI account_creator.py — tidak ada trigger manual dari API.
Jadwal harian dari settings.schedule_time (WIB) dan isi ulang otomatis sampai
settings.standby_target tiap settings.refill_interval_minutes.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

import core.bootstrap  # noqa: F401 — env Firefox, patch Playwright, .env, MMDB (HARUS pertama)
import db
import export_xlsx
import repo
from core import config
from core import domains as domains_mod
from core import proxy as proxy_mod
from core import runner
from models import init_db
from runlog import describe_exc

ROOT = Path(__file__).resolve().parent
TZ = "Asia/Jakarta"
_PROVIDERS = ("kurmamail", "webhook", "local_tempmail", "1secmail", "mailtm", "gptmail")

_RUNNING = threading.Event()     # batch sedang jalan?
_STOP = threading.Event()        # minta batch berhenti setelah attempt berjalan selesai
_CLAIM = threading.Lock()


def _claim_running() -> bool:
    """Atomik check-and-set _RUNNING (cegah dua thread lolos cek bersamaan)."""
    with _CLAIM:
        if _RUNNING.is_set():
            return False
        _RUNNING.set()
        return True


SCHEDULER = BackgroundScheduler(timezone=TZ)
JOBS_ENABLED = config.ENABLE_SCHEDULER   # config.json scheduler.enabled, override env ENABLE_SCHEDULER


def _engine():
    return db.get_engine()


# ── lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = _engine()
    init_db(engine)
    n_stale = repo.mark_stale_running_as_failed(engine)
    if n_stale:
        print(f"startup: {n_stale} run 'running' orphan (dari restart sebelumnya) ditandai failed")
    repo.get_settings(engine)
    if JOBS_ENABLED:
        _setup_scheduler(engine)
        SCHEDULER.start()
    yield
    if SCHEDULER.running:
        SCHEDULER.shutdown(wait=False)


app = FastAPI(title="Kling Account Maker API", lifespan=lifespan)


# ── scheduler ────────────────────────────────────────────────────────────────
def _hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _setup_scheduler(engine) -> None:
    s = repo.get_settings(engine)
    for job in list(SCHEDULER.get_jobs()):
        SCHEDULER.remove_job(job.id)
    if s.get("enable_scheduler", True):
        h, m = _hm(s.get("schedule_time", "03:00"))
        jitter = max(0, int(s.get("schedule_jitter_minutes", 20))) * 60
        SCHEDULER.add_job(job_scheduled, CronTrigger(hour=h, minute=m, timezone=TZ, jitter=jitter or None),
                          id="scheduled", name="Batch harian", misfire_grace_time=3600)
    refill = int(s.get("refill_interval_minutes", 0) or 0)
    if refill > 0 and int(s.get("standby_target", 0) or 0) > 0:
        SCHEDULER.add_job(job_refill, IntervalTrigger(minutes=refill, timezone=TZ),
                          id="auto_refill", name=f"Isi ulang standby tiap {refill}m", misfire_grace_time=600)
    if int(s.get("retention_days", 0) or 0) > 0:
        SCHEDULER.add_job(job_purge, CronTrigger(hour=3, minute=30, timezone=TZ),
                          id="purge", name="Hapus run lama", misfire_grace_time=3600)


def _run_guarded(trigger: str, count: int | None = None) -> bool:
    """Jalankan batch kalau tidak ada yang sedang jalan. Return False kalau sibuk."""
    if not _claim_running():
        return False
    _STOP.clear()
    try:
        runner.run_batch(_engine(), trigger=trigger, count=count, stop_event=_STOP)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        print(f"run_batch error: {describe_exc(e)}")
    finally:
        _RUNNING.clear()
    return True


def job_scheduled() -> None:
    s = repo.effective_settings(_engine())
    if not _run_guarded("scheduled", count=int(s["batch_size"])):
        print("scheduled: skip, batch lain sedang jalan")


def job_refill() -> None:
    engine = _engine()
    s = repo.effective_settings(engine)
    target = int(s["standby_target"])
    if target <= 0:
        return
    if _RUNNING.is_set():
        print("auto_refill: skip, batch lain sedang jalan")
        return
    last = repo.latest_run(engine)
    if last and (last.get("error_message") or "").startswith("NOT_IMPLEMENTED"):
        print("auto_refill: skip, flow site masih stub (run terakhir NOT_IMPLEMENTED)")
        return
    standby = repo.count_by_status(engine, "standby")
    need = target - standby
    if need <= 0:
        print(f"auto_refill: skip, standby {standby} ≥ target {target}")
        return
    if repo.count_success_last_24h(engine) >= int(s["max_daily_success"]):
        print("auto_refill: skip, batas harian tercapai")
        return
    _run_guarded("auto_refill", count=min(need, int(s["batch_size"])))


def job_purge() -> None:
    engine = _engine()
    days = int(repo.get_settings(engine).get("retention_days", 0) or 0)
    if days <= 0:
        return
    ids = repo.purge_old_runs(engine, days)
    for rid in ids:
        try:
            (Path(config.LOG_DIR) / f"run_{rid}.log").unlink()
        except OSError:
            pass
    print(f"purge: {len(ids)} run lebih tua dari {days} hari dihapus")


def _job_next(job_id: str) -> str | None:
    if not SCHEDULER.running:
        return None
    job = SCHEDULER.get_job(job_id)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


# ── helpers ──────────────────────────────────────────────────────────────────
def _rows_to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    if not rows:
        return ""
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict))
                        else v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()})
    return out.getvalue()


def _json_default(o: Any):
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def _attachment(data: bytes | str, filename: str, media_type: str) -> StreamingResponse:
    body = data.encode("utf-8") if isinstance(data, str) else data
    return StreamingResponse(iter([body]), media_type=media_type,
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _usage_or_422(usage: str | None) -> str | None:
    if usage and usage not in repo.USAGE_GROUPS:
        raise HTTPException(status_code=422, detail="usage harus unused | used | unusable")
    return usage


def _status_or_422(status: str | None) -> str | None:
    if status and status not in repo.ACCOUNT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status harus salah satu: {', '.join(repo.ACCOUNT_STATUSES)}")
    return status


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")


def _ids_param(ids: str | None) -> list[int] | None:
    """?ids=1,2,3 → [1,2,3]; kosong → None (semua)."""
    if not ids:
        return None
    out = []
    for part in ids.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise HTTPException(status_code=422, detail="ids harus daftar angka dipisah koma")
        out.append(int(part))
    return out or None


def _ids_body(body: dict) -> list[int]:
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, int) or isinstance(i, bool) for i in ids):
        raise HTTPException(status_code=422, detail="ids harus list angka (minimal 1)")
    if len(ids) > 5000:
        raise HTTPException(status_code=422, detail="maksimal 5000 id per permintaan")
    return ids


# ── routes: health & summary ─────────────────────────────────────────────────
@app.get("/api/health")
def health():
    engine = _engine()
    return {"ok": True, "db": engine.url.get_backend_name().split("+")[0],
            "scheduler_running": bool(SCHEDULER.running), "creator_running": _RUNNING.is_set(),
            "flow_implemented": runner.flow_implemented()}


@app.get("/api/summary")
def summary():
    engine = _engine()
    s = repo.summary(engine)
    settings = repo.get_settings(engine)
    return {
        **s,
        "creator_running": _RUNNING.is_set(),
        "stop_requested": _RUNNING.is_set() and _STOP.is_set(),
        "flow_implemented": runner.flow_implemented(),
        "standby_target": int(settings.get("standby_target", 0) or 0),
        "proxies": {"total": proxy_mod.proxy_count(), "bad": proxy_mod.bad_proxy_count(),
                    "croxy": bool(config.CROXY_BASE_PROXY)},
        "domains": {"total": domains_mod.domain_count(), "banned": len(domains_mod.get_db_banned_domains())},
        "scheduler": {"enabled": JOBS_ENABLED and bool(settings.get("enable_scheduler", True)),
                      "schedule_time": settings.get("schedule_time"),
                      "next_run_at": _job_next("scheduled"), "next_refill_at": _job_next("auto_refill")},
    }


# ── routes: runs ─────────────────────────────────────────────────────────────
@app.get("/api/runs")
def list_runs(limit: int = Query(50, ge=1, le=500)):
    return repo.list_runs(_engine(), limit=limit)


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: int):
    engine = _engine()
    run = repo.get_run(engine, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run["accounts"] = repo.accounts_for_run(engine, run_id)
    return run


@app.get("/api/runs/{run_id}/log")
def get_run_log(run_id: int, tail: int = Query(2000, ge=1, le=20000)):
    """Log run: dari file LOG_DIR (terisi saat run masih jalan), fallback ke kolom DB."""
    run = repo.get_run(_engine(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    text, source = run.get("log") or "", "db"
    path = Path(config.LOG_DIR) / f"run_{run_id}.log"
    try:
        live = path.read_text(encoding="utf-8", errors="replace")
        if len(live) > len(text):
            text, source = live, "file"
    except OSError:
        pass
    lines = text.splitlines()
    return {"run_id": run_id, "status": run["status"], "source": source,
            "truncated": len(lines) > tail, "log": "\n".join(lines[-tail:])}


@app.post("/api/runs/stop")
def stop_run():
    if not _RUNNING.is_set():
        raise HTTPException(status_code=409, detail="Tidak ada batch yang berjalan")
    _STOP.set()
    return {"stopping": True}


# ── routes: accounts ─────────────────────────────────────────────────────────
@app.get("/api/accounts")
def list_accounts(status: str | None = None, usage: str | None = None, q: str | None = None,
                  page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500),
                  sort: str = Query("created_desc")):
    _status_or_422(status); _usage_or_422(usage)
    return repo.list_accounts(_engine(), status=status, q=q, page=page, size=size, sort=sort, usage=usage)


@app.get("/api/accounts/trend")
def accounts_trend(days: int = Query(14, ge=1, le=90)):
    return repo.created_per_day(_engine(), days=days)


@app.get("/api/accounts/export.xlsx")
def export_accounts_xlsx(status: str | None = None, ids: str | None = None, usage: str | None = None):
    _status_or_422(status); _usage_or_422(usage)
    data = export_xlsx.accounts_workbook(repo.export_rows(_engine(), status, _ids_param(ids), usage))
    return _attachment(data, f"accounts-{_stamp()}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/accounts/export.csv")
def export_accounts_csv(status: str | None = None, ids: str | None = None, usage: str | None = None):
    _status_or_422(status); _usage_or_422(usage)
    return _attachment(_rows_to_csv(repo.export_rows(_engine(), status, _ids_param(ids), usage)), f"accounts-{_stamp()}.csv", "text/csv")


@app.get("/api/accounts/export.json")
def export_accounts_json(status: str | None = None, ids: str | None = None, usage: str | None = None):
    _status_or_422(status); _usage_or_422(usage)
    rows = repo.export_rows(_engine(), status, _ids_param(ids), usage)
    return _attachment(json.dumps({"rows": rows}, ensure_ascii=False, default=_json_default, indent=2),
                       f"accounts-{_stamp()}.json", "application/json")


@app.get("/api/export/preview")
def export_preview(status: str | None = None, rows: int = Query(5, ge=1, le=50)):
    _status_or_422(status)
    all_rows = repo.export_rows(_engine(), status)
    cols = list(all_rows[0].keys()) if all_rows else []
    return {"columns": cols, "rows": all_rows[:rows], "total": len(all_rows)}


@app.post("/api/accounts/bulk")
def accounts_bulk(body: dict):
    """Aksi massal: {"ids":[...], "action":"mark_used"|"mark_unused"|"set_status"|"delete", "status"?}.
    mark_used → status 'used'; mark_unused → 'standby'."""
    ids = _ids_body(body)
    action = body.get("action")
    engine = _engine()
    if action == "delete":
        n = repo.delete_accounts(engine, ids)
    elif action in ("mark_used", "mark_unused", "set_status"):
        status = {"mark_used": "used", "mark_unused": "standby"}.get(action, body.get("status"))
        if status not in repo.ACCOUNT_STATUSES:
            raise HTTPException(status_code=422, detail=f"status harus salah satu: {', '.join(repo.ACCOUNT_STATUSES)}")
        n = repo.bulk_set_status(engine, ids, status)
    else:
        raise HTTPException(status_code=422, detail="action harus mark_used | mark_unused | set_status | delete")
    return {"ok": True, "action": action, "affected": n, "counts": repo.account_counts(engine)}


@app.get("/api/accounts/{account_id}")
def get_account(account_id: int):
    acc = repo.get_account(_engine(), account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return acc


@app.get("/api/accounts/{account_id}/cookies")
def account_cookies(account_id: int):
    acc = repo.get_account(_engine(), account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    raw = acc.get("cookies") or "[]"
    try:
        pretty = json.dumps(json.loads(raw), indent=2)
    except ValueError:
        pretty = raw
    return _attachment(pretty, f"cookies-{acc['email']}.json", "application/json")


@app.put("/api/accounts/{account_id}/status")
def set_account_status(account_id: int, body: dict):
    status = body.get("status")
    if status not in repo.ACCOUNT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status harus salah satu: {', '.join(repo.ACCOUNT_STATUSES)}")
    engine = _engine()
    if not repo.set_account_status(engine, account_id, status):
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return repo.get_account(engine, account_id)


# ── routes: testing (khusus admin; proxy webapp memblokir member) ────────────
def _int_in(body: dict, key: str, lo: int, hi: int) -> int | None:
    v = body.get(key)
    if v is None:
        return None
    if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
        raise HTTPException(status_code=422, detail=f"{key} harus bilangan bulat {lo}..{hi}")
    return v


@app.post("/api/test/run")
def test_run(body: dict | None = None):
    """Run manual untuk pengujian di server: {count?, workers?, provider?}. 202 / 409 kalau sibuk."""
    if _RUNNING.is_set():
        raise HTTPException(status_code=409, detail="Creator sedang berjalan")
    body = body or {}
    count = _int_in(body, "count", 1, 100)
    workers = _int_in(body, "workers", 1, 8)
    provider = body.get("provider") or None
    if provider is not None and provider not in _PROVIDERS:
        raise HTTPException(status_code=422, detail="provider tidak valid")
    if not _claim_running():
        raise HTTPException(status_code=409, detail="Creator sedang berjalan")
    _STOP.clear()

    def worker():
        try:
            runner.run_batch(_engine(), trigger="manual", count=count, workers=workers,
                             provider=provider, stop_event=_STOP)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            print(f"run_batch error: {describe_exc(e)}")
        finally:
            _RUNNING.clear()

    threading.Thread(target=worker, daemon=True, name="test-batch").start()
    return JSONResponse({"started": True, "trigger": "manual", "count": count, "workers": workers,
                         "provider": provider}, status_code=202)


@app.get("/api/test/diagnostics")
def test_diagnostics():
    """Cek cepat kesiapan server: DB, config, browser, GeoIP, proxy, domain, flow."""
    engine = _engine()
    out: dict[str, Any] = {"checked_at": datetime.now().isoformat(timespec="seconds")}
    try:
        with engine.connect() as con:
            con.exec_driver_sql("SELECT 1")
        out["db"] = {"ok": True, "backend": engine.url.get_backend_name().split("+")[0]}
    except Exception as e:  # noqa: BLE001
        out["db"] = {"ok": False, "error": describe_exc(e)}
    out["config"] = {"ok": not config.validate(require_password=True), "problems": config.validate(require_password=True),
                     "sources": config.CONFIG_SOURCES, "site": config.SITE_NAME, "signup_url": config.KLING_SIGNUP_URL}
    try:
        from camoufox.pkgman import launch_path, installed_verstr
        out["browser"] = {"ok": True, "path": str(launch_path()), "version": str(installed_verstr())}
    except Exception as e:  # noqa: BLE001
        out["browser"] = {"ok": False, "error": describe_exc(e)}
    try:
        from camoufox.locale import MMDB_FILE
        import geoip2.database
        with geoip2.database.Reader(str(MMDB_FILE)) as r:
            r.city("8.8.8.8")
        out["geoip"] = {"ok": True, "path": str(MMDB_FILE)}
    except Exception as e:  # noqa: BLE001
        out["geoip"] = {"ok": False, "error": describe_exc(e)}
    out["display"] = {"xvfb": bool(os.environ.get("DISPLAY")), "display": os.environ.get("DISPLAY", "")}
    out["proxies"] = {"total": proxy_mod.proxy_count(), "bad": proxy_mod.bad_proxy_count(), "croxy": bool(config.CROXY_BASE_PROXY)}
    out["domains"] = {"total": domains_mod.domain_count(), "banned": len(domains_mod.get_db_banned_domains())}
    out["email"] = {"provider": config.EMAIL_PROVIDER, "chain": provider_chain_safe()}
    if config.KURMAMAIL_URL:
        from core.mail.kurmamail import kurmamail_health
        ok_km, msg_km = kurmamail_health()
        out["kurmamail"] = {"ok": ok_km, "detail": msg_km, "url": config.KURMAMAIL_URL, "api_key": bool(config.KURMAMAIL_API_KEY)}
    out["flow"] = {"implemented": runner.flow_implemented(), "module": f"sites/{config.SITE_NAME}/flow.py"}
    out["creator_running"] = _RUNNING.is_set()
    out["last_run"] = repo.latest_run(engine)
    return out


def provider_chain_safe() -> list[str]:
    try:
        from core.mail import provider_chain
        return provider_chain()
    except Exception:  # noqa: BLE001
        return []


@app.post("/api/test/mail")
def test_mail(body: dict | None = None):
    """Uji provider email: buat 1 mailbox sementara (tanpa menunggu OTP). {provider?}"""
    provider = (body or {}).get("provider") or None
    if provider is not None and provider not in _PROVIDERS:
        raise HTTPException(status_code=422, detail="provider tidak valid")
    from core.mail import make_mail_client
    disabled: set[str] = set()
    t0 = datetime.now()
    client = make_mail_client(provider, disabled)
    ms = int((datetime.now() - t0).total_seconds() * 1000)
    if client is None:
        return {"ok": False, "provider": provider, "tried_failed": sorted(disabled), "ms": ms}
    return {"ok": True, "provider": client.mode, "email": client.email, "skipped": sorted(disabled), "ms": ms}


# ── routes: settings ─────────────────────────────────────────────────────────
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_INT_RANGES = (("workers", 1, 16), ("batch_size", 1, 500), ("max_daily_success", 1, 100000),
               ("standby_target", 0, 100000), ("refill_interval_minutes", 0, 1440),
               ("schedule_jitter_minutes", 0, 120), ("max_attempts_per_slot", 1, 20),
               ("delay_between_accounts", 0, 600), ("browser_concurrency", 1, 8), ("retention_days", 0, 3650))
_BOOLS = ("enable_scheduler", "debug_screenshots")


@app.get("/api/settings")
def get_settings_endpoint():
    return repo.get_settings(_engine())


@app.put("/api/settings")
def update_settings(body: dict):
    for key, lo, hi in _INT_RANGES:
        if key in body and (not isinstance(body[key], int) or isinstance(body[key], bool) or not lo <= body[key] <= hi):
            raise HTTPException(status_code=422, detail=f"{key} harus bilangan bulat {lo}..{hi}")
    for key in _BOOLS:
        if key in body and not isinstance(body[key], bool):
            raise HTTPException(status_code=422, detail=f"{key} harus boolean")
    if "schedule_time" in body and (not isinstance(body["schedule_time"], str) or not _HHMM.match(body["schedule_time"])):
        raise HTTPException(status_code=422, detail="schedule_time harus HH:MM")
    if "email_provider" in body and body["email_provider"] not in _PROVIDERS:
        raise HTTPException(status_code=422, detail=f"email_provider harus salah satu: {', '.join(_PROVIDERS)}")
    engine = _engine()
    result = repo.save_settings(engine, body)
    if SCHEDULER.running:
        _setup_scheduler(engine)
    return result


# ── routes: proxies & domains (read-only, dari env/file) ─────────────────────
@app.get("/api/proxies")
def proxies_info():
    return {"total": proxy_mod.proxy_count(), "bad": proxy_mod.bad_proxy_count(), "croxy": bool(config.CROXY_BASE_PROXY)}


@app.get("/api/domains")
def domains_info():
    return {"domains": list(domains_mod.CUSTOM_DOMAINS), "banned": domains_mod.get_db_banned_domains()}


# ── users (dipanggil webapp server-side; proxy browser memblokir /users & /auth) ──
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_MIN_PASSWORD = 8


def _check_password_body(body: dict) -> str:
    pw = body.get("password")
    if not isinstance(pw, str) or len(pw) < _MIN_PASSWORD:
        raise HTTPException(status_code=422, detail=f"Password minimal {_MIN_PASSWORD} karakter")
    return pw


@app.get("/api/users")
def list_users():
    return repo.list_users(_engine())


@app.post("/api/users", status_code=201)
def create_user(body: dict):
    username = str(body.get("username") or "").strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=422, detail="Username 3–32 karakter: huruf, angka, titik, _ atau -")
    pw = _check_password_body(body)
    role = body.get("role", "member")
    if role not in repo.USER_ROLES:
        raise HTTPException(status_code=422, detail="role harus admin | member")
    engine = _engine()
    env_admin = os.getenv("DASHBOARD_USER", "").strip()
    if (env_admin and username.lower() == env_admin.lower()) or repo.user_exists(engine, username):
        raise HTTPException(status_code=409, detail="Username sudah dipakai")
    return repo.create_user(engine, username, pw, role)


@app.put("/api/users/{user_id}/role")
def change_role(user_id: int, body: dict):
    role = body.get("role")
    if role not in repo.USER_ROLES:
        raise HTTPException(status_code=422, detail="role harus admin | member")
    if not repo.set_role(_engine(), user_id, role):
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return {"ok": True, "role": role}


@app.put("/api/users/{user_id}/password")
def change_password(user_id: int, body: dict):
    pw = _check_password_body(body)
    if not repo.set_password(_engine(), user_id, pw):
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return {"ok": True}


@app.delete("/api/users/{user_id}")
def remove_user(user_id: int):
    if not repo.delete_user(_engine(), user_id):
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return {"ok": True}


@app.post("/api/auth/verify")
def verify_login(body: dict):
    username, pw = body.get("username"), body.get("password")
    if not isinstance(username, str) or not isinstance(pw, str):
        return {"ok": False}
    return {"ok": repo.verify_user(_engine(), username.strip(), pw)}


@app.get("/api/auth/user-exists")
def auth_user_exists(username: str = Query(..., min_length=1, max_length=64)):
    """Dipanggil middleware webapp tiap request: user masih ada? + role terkini (hak akses live)."""
    u = next((x for x in repo.list_users(_engine()) if x["username"] == username), None)
    return {"exists": u is not None, "role": (u or {}).get("role")}
