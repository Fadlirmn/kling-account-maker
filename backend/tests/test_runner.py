import threading

import pytest
from sqlalchemy import create_engine

import repo
from core import runner
from core.runner import AccountResult
from models import init_db


@pytest.fixture
def eng(monkeypatch, tmp_path):
    e = create_engine("sqlite:///:memory:")
    init_db(e)
    from core import config
    monkeypatch.setattr(config, "KLING_DEFAULT_PASSWORD", "Pw#12345")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    monkeypatch.setattr(config, "RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr(config, "COOKIES_DIR", tmp_path)
    monkeypatch.setattr(runner, "get_safe_workers", lambda n: n)
    # default config.json = kurmamail (butuh kredensial) → tes pakai provider publik
    repo.save_settings(e, {"email_provider": "1secmail"})
    return e


def _patch_slot(monkeypatch, fn):
    monkeypatch.setattr(runner, "run_slot", fn)


def test_run_batch_sukses(eng, monkeypatch):
    def slot(i, provider, max_attempts, stop, rl):
        return AccountResult(email=f"a{i}@x.id", success=True, status="standby", user_id=f"u{i}", attempts=1,
                             cookies=[{"name": "s", "value": "1"}])
    _patch_slot(monkeypatch, slot)
    rid = runner.run_batch(eng, "manual", count=3, workers=2, provider="1secmail", log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "success" and r["created_ok"] == 3 and r["failed"] == 0 and r["error_message"] is None
    assert "STANDBY OK — a1@x.id" in r["log"] and r["log"].rstrip().endswith("(ok=3 failed=0 skipped=0) ===")
    assert repo.count_by_status(eng, "standby") == 3
    assert all(a["run_id"] == rid for a in repo.accounts_for_run(eng, rid))


def test_run_batch_partial_dan_error_message(eng, monkeypatch):
    def slot(i, provider, max_attempts, stop, rl):
        if i == 1:
            return AccountResult(email="ok@x.id", success=True, status="standby", attempts=1)
        return AccountResult(email=f"f{i}@x.id", error="otp timeout", attempts=max_attempts)
    _patch_slot(monkeypatch, slot)
    rid = runner.run_batch(eng, "scheduled", count=3, workers=1, log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "partial" and r["created_ok"] == 1 and r["failed"] == 2
    assert r["error_message"].startswith("2 slot gagal") and "otp timeout" in r["error_message"]
    assert repo.account_counts(eng)["failed"] == 2


def test_run_batch_not_implemented_fatal(eng, monkeypatch):
    calls = []

    def slot(i, provider, max_attempts, stop, rl):
        calls.append(i)
        if stop.is_set():
            return AccountResult(email="", error="aborted")
        return AccountResult(email=f"s{i}@x.id", error="NOT_IMPLEMENTED", attempts=1)
    _patch_slot(monkeypatch, slot)
    rid = runner.run_batch(eng, "manual", count=4, workers=1, log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "failed"
    assert r["error_message"].startswith("NOT_IMPLEMENTED")
    assert r["failed"] >= 1 and r["failed"] + r["skipped"] == 4
    assert "GAGAL — NOT_IMPLEMENTED" in r["log"] and "fatal:" in r["log"]


def test_run_batch_stop_event(eng, monkeypatch):
    stop = threading.Event()

    def slot(i, provider, max_attempts, stop_ev, rl):
        if i == 1:
            stop_ev.set()
            return AccountResult(email="a@x.id", success=True, status="standby")
        return AccountResult(email="", error="aborted")
    _patch_slot(monkeypatch, slot)
    rid = runner.run_batch(eng, "manual", count=3, workers=1, stop_event=stop, log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "partial" and r["created_ok"] == 1 and r["skipped"] == 2 and r["failed"] == 0


def test_run_batch_daily_limit(eng, monkeypatch):
    repo.save_settings(eng, {"max_daily_success": 2})
    repo.upsert_account(eng, {"email": "x1@x.id", "status": "standby"})
    repo.upsert_account(eng, {"email": "x2@x.id", "status": "standby"})
    _patch_slot(monkeypatch, lambda *a: pytest.fail("tidak boleh ada slot"))
    rid = runner.run_batch(eng, "auto_refill", count=5, workers=1, log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "success" and r["skipped"] == 5 and r["created_ok"] == 0
    assert "batas harian tercapai" in r["log"]


def test_run_batch_konfigurasi_kurang(eng, monkeypatch):
    from core import config
    monkeypatch.setattr(config, "KLING_DEFAULT_PASSWORD", "")
    _patch_slot(monkeypatch, lambda *a: pytest.fail("tidak boleh ada slot"))
    rid = runner.run_batch(eng, "manual", count=1, workers=1, log=lambda _l: None)
    r = repo.get_run(eng, rid)
    assert r["status"] == "failed" and "KLING_DEFAULT_PASSWORD" in r["error_message"]


def test_decide():
    assert runner._decide("NOT_IMPLEMENTED", None) == (False, 0)
    assert runner._decide("PROXY_FLAGGED", None) == (True, 15)
    assert runner._decide("email input not found", None) == (True, 5)
    assert runner._decide("aborted", None) == (False, 0)


def test_run_batch_provider_eksplisit_menang(eng, monkeypatch):
    """settings=webhook (tanpa worker URL) tapi run diminta mailtm → validasi memakai mailtm, bukan gagal."""
    from core import config
    repo.save_settings(eng, {"email_provider": "webhook"})
    monkeypatch.setattr(config, "CLOUDFLARE_WORKER_URL", "")
    seen = {}

    def slot(i, provider, max_attempts, stop, rl):
        seen["provider"] = provider
        return AccountResult(email="ok@x.id", success=True, status="standby")
    _patch_slot(monkeypatch, slot)
    rid = runner.run_batch(eng, "manual", count=1, workers=1, provider="mailtm", log=lambda _l: None)
    assert repo.get_run(eng, rid)["status"] == "success" and seen["provider"] == "mailtm"
