from datetime import datetime, timezone

from core import config
from core.mail.kurmamail import KurmaMail


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p


def test_kurmamail_create_dan_poll_otp(monkeypatch):
    monkeypatch.setattr(config, "KURMAMAIL_URL", "https://mail.test")
    monkeypatch.setattr(config, "KURMAMAIL_API_KEY", "km_x")
    monkeypatch.setattr(config, "CUSTOM_DOMAINS", ["k.test"])
    monkeypatch.setattr(config, "MAIL_SENDER_FILTER", ["kling"])
    monkeypatch.setattr(config, "OTP_PHRASES", [])
    monkeypatch.setattr("core.mail.kurmamail.next_domain", lambda: "k.test")
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return _Resp(200, {"to": params["to"], "count": 2, "emails": [
            {"id": "1", "sender_email": "promo@spam.test", "subject": "halo", "body_text": "kode 111111"},
            {"id": "2", "sender_email": "noreply@klingai.com", "subject": "Kling verification code",
             "body_text": "Your verification code is 482913", "body_html": "", "created_at": datetime.now(timezone.utc).isoformat()},
        ]})
    monkeypatch.setattr("core.mail.kurmamail.requests.get", fake_get)

    c = KurmaMail()
    assert KurmaMail.available() and c.create()
    assert c.email.startswith(config.EMAIL_PREFIX) and c.email.endswith("@k.test")
    assert c.poll_otp(timeout=5) == "482913"
    url, params, headers = calls[0]
    assert url == "https://mail.test/api/emails/lookup" and params["to"] == c.email and headers["X-API-Key"] == "km_x"


def test_kurmamail_tidak_tersedia_tanpa_kredensial(monkeypatch):
    monkeypatch.setattr(config, "KURMAMAIL_URL", "")
    monkeypatch.setattr(config, "KURMAMAIL_API_KEY", "")
    assert not KurmaMail.available()
    from core.mail import provider_chain
    assert "kurmamail" not in provider_chain("1secmail")
