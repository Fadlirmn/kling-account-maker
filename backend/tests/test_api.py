import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import api
import db
import repo
from core import runner
from models import init_db


@pytest.fixture
def test_engine():
    # StaticPool + check_same_thread=False: TestClient menjalankan endpoint di thread lain,
    # :memory: default akan jadi DB berbeda per koneksi.
    e = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    init_db(e)
    return e


@pytest.fixture
def client(test_engine, monkeypatch):
    monkeypatch.setattr(db, "get_engine", lambda: test_engine)
    return TestClient(api.app)


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True and r.json()["db"] == "sqlite"
    assert r.json()["creator_running"] is False and r.json()["flow_implemented"] is False


def test_summary_kosong(client):
    d = client.get("/api/summary").json()
    assert d["last_run"] is None and d["standby"] == 0 and d["total"] == 0
    assert "proxies" in d and "scheduler" in d and d["standby_target"] == 20


def test_settings_validation(client):
    assert client.put("/api/settings", json={"workers": 0}).status_code == 422
    assert client.put("/api/settings", json={"workers": True}).status_code == 422
    assert client.put("/api/settings", json={"schedule_time": "3:00"}).status_code == 422
    assert client.put("/api/settings", json={"email_provider": "yahoo"}).status_code == 422
    assert client.put("/api/settings", json={"enable_scheduler": "yes"}).status_code == 422
    r = client.put("/api/settings", json={"workers": 3, "schedule_time": "05:30", "email_provider": "mailtm"})
    assert r.status_code == 200
    assert r.json()["workers"] == 3 and r.json()["schedule_time"] == "05:30" and r.json()["config_version"] == 2


def test_runs_concurrent_guard(client, monkeypatch):
    calls = []

    def slow_run(engine, trigger="manual", count=None, workers=None, provider=None, stop_event=None, log=print):
        calls.append((trigger, count, workers))
        time.sleep(0.3)
        return 1

    monkeypatch.setattr(runner, "run_batch", slow_run)
    assert client.post("/api/runs/stop").status_code == 409
    r1 = client.post("/api/runs", json={"trigger": "manual", "count": 2, "workers": 1})
    assert r1.status_code == 202 and r1.json()["count"] == 2
    assert client.post("/api/runs", json={"trigger": "manual"}).status_code == 409
    assert client.post("/api/runs/stop").status_code == 200
    time.sleep(0.5)
    assert calls == [("manual", 2, 1)]
    assert client.post("/api/runs", json={"trigger": "ngaco"}).status_code == 422
    assert client.post("/api/runs", json={"count": 0}).status_code == 422
    assert client.post("/api/runs", json={"trigger": "manual"}).status_code == 202
    time.sleep(0.5)


def test_runs_dan_log(client, test_engine, tmp_path, monkeypatch):
    from core import config
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    rid = repo.create_run(test_engine, "manual", 1, 1, "1secmail", 1)
    repo.upsert_account(test_engine, {"email": "a@x.id", "status": "standby"}, rid)
    repo.finish_run(test_engine, rid, "success", 1, log="=== run ===\n[00:00:00] [+0.1s] INFO  ok")
    runs = client.get("/api/runs").json()
    assert len(runs) == 1 and "log" not in runs[0]
    d = client.get(f"/api/runs/{rid}").json()
    assert d["status"] == "success" and d["accounts"][0]["email"] == "a@x.id"
    lg = client.get(f"/api/runs/{rid}/log").json()
    assert lg["source"] == "db" and "INFO  ok" in lg["log"]
    (tmp_path / f"run_{rid}.log").write_text("=== run ===\n" + "\n".join(f"baris{i} panjang supaya lebih besar dari log DB" for i in range(1, 4)) + "\n")
    lg = client.get(f"/api/runs/{rid}/log?tail=2").json()
    assert lg["source"] == "file" and lg["truncated"] is True and lg["log"].startswith("baris2") and lg["log"].count("\n") == 1
    assert client.get("/api/runs/999").status_code == 404


def test_accounts_list_filter_export(client, test_engine):
    repo.upsert_account(test_engine, {"email": "a@x.id", "status": "standby", "password": "p",
                                      "cookies": [{"name": "s", "value": "1"}]})
    repo.upsert_account(test_engine, {"email": "b@x.id", "status": "failed", "error": "otp timeout"})
    d = client.get("/api/accounts").json()
    assert d["total"] == 2 and d["counts"]["standby"] == 1
    assert client.get("/api/accounts?status=standby").json()["total"] == 1
    assert client.get("/api/accounts?status=ngaco").status_code == 422
    assert client.get("/api/accounts?q=b@").json()["items"][0]["email"] == "b@x.id"
    aid = [i for i in d["items"] if i["email"] == "a@x.id"][0]["id"]
    acc = client.get(f"/api/accounts/{aid}").json()
    assert acc["password"] == "p" and acc["has_cookies"] is True
    ck = client.get(f"/api/accounts/{aid}/cookies")
    assert ck.status_code == 200 and "attachment" in ck.headers["content-disposition"]
    assert client.put(f"/api/accounts/{aid}/status", json={"status": "banned"}).json()["status"] == "banned"
    assert client.put(f"/api/accounts/{aid}/status", json={"status": "x"}).status_code == 422
    csv_ = client.get("/api/accounts/export.csv")
    assert csv_.status_code == 200 and "email" in csv_.text and "has_cookies" in csv_.text
    assert client.get("/api/accounts/export.xlsx").status_code == 200
    js = client.get("/api/accounts/export.json")
    assert js.status_code == 200 and len(js.json()["rows"]) == 2
    pv = client.get("/api/export/preview?rows=1").json()
    assert pv["total"] == 2 and len(pv["rows"]) == 1 and "email" in pv["columns"]
    trend = client.get("/api/accounts/trend?days=7").json()
    assert len(trend) == 7 and trend[-1]["created"] == 0  # a@ sudah banned → tidak dihitung
    assert client.get("/api/accounts/999").status_code == 404


def test_users_dan_auth(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    assert client.post("/api/users", json={"username": "ab", "password": "x"}).status_code == 422
    assert client.post("/api/users", json={"username": "admin", "password": "rahasia123"}).status_code == 409
    r = client.post("/api/users", json={"username": "ops", "password": "rahasia123"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert client.post("/api/users", json={"username": "ops", "password": "rahasia123"}).status_code == 409
    assert client.post("/api/auth/verify", json={"username": "ops", "password": "rahasia123"}).json()["ok"] is True
    assert client.get("/api/auth/user-exists?username=ops").json()["exists"] is True
    assert client.put(f"/api/users/{uid}/password", json={"password": "baru12345"}).json()["ok"] is True
    assert client.delete(f"/api/users/{uid}").json()["ok"] is True
    assert client.delete(f"/api/users/{uid}").status_code == 404


def test_accounts_bulk_dan_export_ids(client, test_engine):
    for i in range(4):
        repo.upsert_account(test_engine, {"email": f"b{i}@x.id", "status": "standby", "password": "Pw#12345"})
    ids = [a["id"] for a in client.get("/api/accounts").json()["items"]]
    r = client.post("/api/accounts/bulk", json={"ids": ids[:2], "action": "mark_used"})
    assert r.status_code == 200 and r.json()["affected"] == 2 and r.json()["counts"]["used"] == 2
    r = client.post("/api/accounts/bulk", json={"ids": ids[:1], "action": "mark_unused"})
    assert r.json()["counts"]["used"] == 1 and r.json()["counts"]["standby"] == 3
    r = client.post("/api/accounts/bulk", json={"ids": ids[2:3], "action": "set_status", "status": "banned"})
    assert r.json()["counts"]["banned"] == 1
    assert client.post("/api/accounts/bulk", json={"ids": [], "action": "delete"}).status_code == 422
    assert client.post("/api/accounts/bulk", json={"ids": ids[:1], "action": "ngaco"}).status_code == 422
    csv_ = client.get(f"/api/accounts/export.csv?ids={ids[0]},{ids[1]}").text
    assert csv_.count("@x.id") == 2
    assert client.get("/api/accounts/export.csv?ids=a,b").status_code == 422
    r = client.post("/api/accounts/bulk", json={"ids": ids[3:], "action": "delete"})
    assert r.json()["affected"] == 1 and client.get("/api/accounts").json()["total"] == 3


def test_accounts_usage_filter(client, test_engine):
    for em, st in (("a@x.id", "standby"), ("b@x.id", "used"), ("c@x.id", "failed"), ("d@x.id", "active")):
        repo.upsert_account(test_engine, {"email": em, "status": st})
    assert client.get("/api/accounts?usage=unused").json()["total"] == 2
    assert client.get("/api/accounts?usage=used").json()["total"] == 1
    assert client.get("/api/accounts?usage=unusable").json()["total"] == 1
    assert client.get("/api/accounts?usage=ngaco").status_code == 422
    assert client.get("/api/accounts/export.csv?usage=unused").text.count("@x.id") == 2
