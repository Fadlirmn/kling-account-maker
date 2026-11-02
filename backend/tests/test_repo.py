import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text

import repo
from models import init_db, _ensure_columns


@pytest.fixture
def eng():
    e = create_engine("sqlite:///:memory:")
    init_db(e)
    return e


def test_settings_default_dan_version(eng):
    s = repo.get_settings(eng)
    assert s["batch_size"] == 10 and s["config_version"] == 1
    s2 = repo.save_settings(eng, {"batch_size": 3})
    assert s2["batch_size"] == 3 and s2["config_version"] == 2
    s3 = repo.save_settings(eng, {"standby_target": 50})   # bukan konfigurasi pembuatan → tidak bump
    assert s3["config_version"] == 2 and s3["standby_target"] == 50
    assert repo.save_settings(eng, {"tidak_ada": 1})["config_version"] == 2


def test_effective_settings_clamp(eng):
    repo.save_settings(eng, {"workers": 0, "browser_concurrency": 0})
    s = repo.effective_settings(eng)
    assert s["workers"] == 1 and s["browser_concurrency"] == 1


def test_run_lifecycle(eng):
    rid = repo.create_run(eng, "manual", 5, 2, "1secmail", 1)
    assert repo.get_run(eng, rid)["status"] == "running"
    repo.finish_run(eng, rid, "partial", 3, 2, 0, "2 slot gagal: 2×otp timeout", "=== log ===")
    r = repo.get_run(eng, rid)
    assert r["status"] == "partial" and r["created_ok"] == 3 and r["log"].startswith("===")
    assert r["finished_at"] is not None and r["finished_at"].tzinfo is not None
    lst = repo.list_runs(eng)
    assert len(lst) == 1 and "log" not in lst[0]
    assert repo.latest_run(eng)["id"] == rid
    assert repo.latest_run(eng, repo.OK_STATUSES)["id"] == rid


def test_mark_stale_running_as_failed(eng):
    r_running = repo.create_run(eng, "manual", 1, 1, None, 1)
    r_ok = repo.create_run(eng, "manual", 1, 1, None, 1)
    repo.finish_run(eng, r_ok, "success", 1)
    assert repo.mark_stale_running_as_failed(eng) == 1
    assert repo.get_run(eng, r_running)["status"] == "failed"
    assert repo.get_run(eng, r_ok)["status"] == "success"


def test_upsert_account_dan_counts(eng):
    rid = repo.create_run(eng, "manual", 1, 1, None, 1)
    repo.upsert_account(eng, {"email": "A@x.id", "password": "p", "status": "standby",
                              "cookies": [{"name": "s", "value": "1"}]}, rid)
    repo.upsert_account(eng, {"email": "a@x.id", "status": "active", "user_id": "u1"}, rid)  # update by email (lower)
    repo.upsert_account(eng, {"email": "b@x.id", "status": "failed", "error": "otp timeout"}, rid)
    page = repo.list_accounts(eng)
    assert page["total"] == 2
    a = repo.get_account(eng, [i for i in page["items"] if i["email"] == "a@x.id"][0]["id"])
    assert a["status"] == "active" and a["user_id"] == "u1" and a["has_cookies"] is False  # cookies kosong di update
    assert repo.account_counts(eng)["active"] == 1 and repo.account_counts(eng)["failed"] == 1
    assert repo.count_success_last_24h(eng) == 1 and repo.count_failed_last_24h(eng) == 1
    assert repo.list_accounts(eng, status="failed")["total"] == 1
    assert repo.list_accounts(eng, q="u1")["total"] == 1
    assert [r["email"] for r in repo.accounts_for_run(eng, rid)] == ["a@x.id", "b@x.id"]
    assert repo.set_account_status(eng, a["id"], "banned") and repo.get_account(eng, a["id"])["status"] == "banned"
    with pytest.raises(ValueError):
        repo.set_account_status(eng, a["id"], "ngaco")
    rows = repo.export_rows(eng)
    assert "cookies" not in rows[0] and "has_cookies" in rows[0]


def test_created_per_day(eng):
    repo.upsert_account(eng, {"email": "a@x.id", "status": "standby"})
    repo.upsert_account(eng, {"email": "b@x.id", "status": "failed"})
    trend = repo.created_per_day(eng, days=3)
    assert len(trend) == 3
    assert trend[-1]["created"] == 1 and trend[-1]["failed"] == 1
    assert trend[0]["created"] == 0


def test_banned_domains(eng):
    repo.ban_domain(eng, "X.biz.id")
    repo.ban_domain(eng, "x.biz.id")
    assert repo.list_banned_domains(eng) == ["x.biz.id"]


def test_users(eng):
    u = repo.create_user(eng, "ops", "rahasia123")
    assert repo.user_exists(eng, "ops") and repo.verify_user(eng, "ops", "rahasia123")
    assert not repo.verify_user(eng, "ops", "salah") and not repo.verify_user(eng, "ghost", "x")
    assert repo.set_password(eng, u["id"], "baru12345") and repo.verify_user(eng, "ops", "baru12345")
    assert repo.delete_user(eng, u["id"]) and not repo.user_exists(eng, "ops")


def test_purge_old_runs(eng):
    rid = repo.create_run(eng, "manual", 1, 1, None, 1)
    repo.upsert_account(eng, {"email": "a@x.id", "status": "standby"}, rid)
    with eng.begin() as con:
        con.execute(text("UPDATE runs SET started_at = :t"), {"t": datetime.now(timezone.utc) - timedelta(days=40)})
    assert repo.purge_old_runs(eng, 30) == [rid]
    assert repo.get_run(eng, rid) is None
    assert repo.list_accounts(eng)["items"][0]["run_id"] is None


def test_ensure_columns_sqlite_lama():
    """DB SQLite dari core/db.py lama tidak punya run_id/error → migrasi menambahkannya."""
    e = create_engine("sqlite:///:memory:")
    with e.begin() as con:
        con.execute(text("CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT)"))
        # skema persis core/db.py lama (tanpa run_id/error)
        con.execute(text("""CREATE TABLE kling_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT DEFAULT '',
            user_id TEXT DEFAULT '', otp TEXT DEFAULT '', cookies TEXT DEFAULT '', proxy TEXT DEFAULT '',
            email_mode TEXT DEFAULT '', status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
            credits TEXT DEFAULT '', plan TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        con.execute(text("INSERT INTO kling_accounts (email, status) VALUES ('old@x.id', 'standby')"))
    _ensure_columns(e)
    with e.connect() as con:
        cols = {r[1] for r in con.execute(text('PRAGMA table_info("kling_accounts")'))}
    assert {"run_id", "error"} <= cols
    assert repo.list_accounts(e)["items"][0]["email"] == "old@x.id"
