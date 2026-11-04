"""
core.mail.webhook — custom domain + Cloudflare Email Routing (catch-all) → Worker → Cloudflared_webhook.

Receiver = repo Cloudflared_webhook (FastAPI, webhook_receiver.py). Email prefix `kling_` di-route ke KLING_DB
di receiver; OTP 6-digit diekstrak di sana (extract_kling_otp).

Email: {EMAIL_PREFIX}{random10}@{domain dari core.domains} (domain.txt = pool Domain-manage).
OTP:   GET {CLOUDFLARE_WORKER_URL}{WEBHOOK_OTP_PATH}?email=...  → {"status":"success","otp":"123456","service":"Kling AI"}
       (receiver menghapus OTP setelah diambil; "pending" = belum masuk)
Health: GET {CLOUDFLARE_WORKER_URL}/health → {"status":"healthy","databases":{...}}
"""
import random
import string
import time
from typing import Optional

import requests

from core import config
from core.domains import next_domain
from core.mail.base import MailClient


class WebhookMail(MailClient):
    mode = "webhook"

    @staticmethod
    def available() -> bool:
        return bool(config.CLOUDFLARE_WORKER_URL and config.CUSTOM_DOMAINS)

    def create(self) -> bool:
        if not self.available():
            return False
        domain = next_domain()
        if not domain:
            return False
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{config.EMAIL_PREFIX}{suffix}@{domain}"
        self.extra = {"domain": domain}
        return True

    def poll_message(self, timeout: int) -> Optional[dict]:
        # Worker hanya menyimpan OTP terekstrak, bukan email penuh.
        otp = self._poll(timeout)
        return {"id": "", "from": "webhook", "subject": "", "content": otp, "html": "", "raw": otp} if otp else None

    def poll_otp(self, timeout: int = None) -> str:
        return self._poll(timeout or config.OTP_TIMEOUT)

    def _poll(self, timeout: int) -> str:
        base = config.CLOUDFLARE_WORKER_URL
        endpoints = [config.WEBHOOK_OTP_PATH]
        if "/get-otp" not in endpoints:
            endpoints.append("/get-otp")
        deadline = time.time() + timeout
        while time.time() < deadline:
            for ep in endpoints:
                try:
                    r = requests.get(f"{base}{ep}", params={"email": self.email}, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("status") == "success":
                            otp = str(data.get("otp", "")).strip()
                            if otp:
                                print()
                                return otp
                        break  # endpoint ada tapi belum ada OTP → jangan coba endpoint lain
                except Exception:
                    pass
            left = int(deadline - time.time())
            if left > 0:
                print(f"    ⏳ Menunggu OTP webhook... ({left}s)", end="\r", flush=True)
                time.sleep(5)
        print()
        return ""


def webhook_simulate(email: str, otp: Optional[str] = None) -> tuple[bool, dict]:
    """Testing: simulasikan email OTP masuk ke receiver (POST /webhook/email) tanpa kirim email asli."""
    if not config.CLOUDFLARE_WORKER_URL:
        return False, {"message": "CLOUDFLARE_WORKER_URL kosong"}
    otp = otp or "".join(random.choices(string.digits, k=6))
    try:
        r = requests.post(
            f"{config.CLOUDFLARE_WORKER_URL}/webhook/email",
            json={"to": email, "subject": "Kling AI verification code (test)",
                  "body": f"Your Kling verification code is {otp}. This code expires in 10 minutes."},
            timeout=10,
        )
        data = r.json() if r.content else {}
        return r.status_code == 200 and data.get("status") == "success", data
    except Exception as e:
        return False, {"message": str(e)}


def webhook_peek(email: str) -> dict:
    """Testing: lihat status OTP tersimpan di receiver tanpa menghapusnya (GET /peek)."""
    if not config.CLOUDFLARE_WORKER_URL:
        return {"ok": False, "message": "CLOUDFLARE_WORKER_URL kosong"}
    try:
        r = requests.get(f"{config.CLOUDFLARE_WORKER_URL}/peek", params={"email": email}, timeout=10)
        data = r.json() if r.content else {}
        return {"ok": r.status_code == 200, **data}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def webhook_stats() -> dict:
    """Testing: riwayat/statistik email yang diterima receiver, semua service (GET /stats)."""
    if not config.CLOUDFLARE_WORKER_URL:
        return {"ok": False, "message": "CLOUDFLARE_WORKER_URL kosong"}
    try:
        r = requests.get(f"{config.CLOUDFLARE_WORKER_URL}/stats", timeout=10)
        data = r.json() if r.content else {}
        return {"ok": r.status_code == 200, **data}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def webhook_health() -> tuple[bool, str]:
    """Cek /health receiver Cloudflared_webhook (dipakai diagnosa). Return (ok, pesan)."""
    if not config.CLOUDFLARE_WORKER_URL:
        return False, "CLOUDFLARE_WORKER_URL kosong"
    try:
        t0 = time.time()
        r = requests.get(f"{config.CLOUDFLARE_WORKER_URL}/health", timeout=8)
        ms = int((time.time() - t0) * 1000)
        status = ""
        try:
            data = r.json()
            status = str(data.get("status", ""))
            kling_db = next((v for k, v in (data.get("databases") or {}).items() if "kling" in k.lower()), None)
            if kling_db is not None and kling_db != "ok":
                return False, f"HTTP {r.status_code} {status}; KLING_DB {kling_db} ({ms} ms)"
        except ValueError:
            pass
        ok = r.status_code == 200 and status in ("", "healthy")
        return ok, f"HTTP {r.status_code} {status} ({ms} ms)".replace("  ", " ")
    except Exception as e:
        return False, str(e)
