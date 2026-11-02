"""Provider webhook ↔ receiver Cloudflared_webhook: alamat kling_<acak>@<domain>, poll /get-otp, health."""
import pytest

from core import config
from core.mail import webhook as wh


class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data if data is not None else {}

    def json(self):
        return self._data


@pytest.fixture
def receiver(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_WORKER_URL", "http://receiver.test")
    monkeypatch.setattr(config, "CUSTOM_DOMAINS", ["a.biz.id"])
    monkeypatch.setattr(config, "EMAIL_PREFIX", "kling_")
    monkeypatch.setattr(wh, "next_domain", lambda: "a.biz.id")
    monkeypatch.setattr(wh.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/health"):
            return _Resp(200, {"status": "healthy", "databases": {"/app/kling_data/kling_accounts.db": "ok"}})
        if url.endswith("/get-otp"):
            # OTP baru muncul di panggilan kedua; receiver pakai format {"status","otp","service"}
            n = sum(1 for u, _ in calls if u.endswith("/get-otp"))
            if n >= 2:
                return _Resp(200, {"status": "success", "otp": "482913", "service": "Kling AI"})
            return _Resp(200, {"status": "pending", "otp": "", "service": "Kling AI"})
        return _Resp(404)

    monkeypatch.setattr(wh.requests, "get", fake_get)
    return calls


def test_create_alamat_prefix_kling(receiver):
    m = wh.WebhookMail()
    assert wh.WebhookMail.available()
    assert m.create()
    local, domain = m.email.split("@")
    assert local.startswith("kling_") and len(local) == len("kling_") + 10
    assert domain == "a.biz.id" and m.extra["domain"] == "a.biz.id"


def test_poll_otp_dari_get_otp(receiver):
    m = wh.WebhookMail()
    m.create()
    assert m.poll_otp(timeout=30) == "482913"
    urls = [u for u, p in receiver if u.endswith("/get-otp")]
    assert urls and all(p == {"email": m.email} for u, p in receiver if u.endswith("/get-otp"))


def test_health_receiver(receiver):
    ok, msg = wh.webhook_health()
    assert ok and "healthy" in msg


def test_health_kling_db_error(receiver, monkeypatch):
    monkeypatch.setattr(wh.requests, "get", lambda *a, **k: _Resp(200, {"status": "degraded", "databases": {"/app/kling_data/kling_accounts.db": "error: locked"}}))
    ok, msg = wh.webhook_health()
    assert not ok and "KLING_DB" in msg


def test_tidak_tersedia_tanpa_url(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_WORKER_URL", "")
    assert not wh.WebhookMail.available()
    assert wh.webhook_health() == (False, "CLOUDFLARE_WORKER_URL kosong")
