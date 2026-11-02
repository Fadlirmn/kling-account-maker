"""
core.mail.kurmamail — Kurma Mail (email-custom, Next.js + Postgres) sebagai sumber OTP.

Alur: alamat acak {EMAIL_PREFIX}{rand}@{domain} → Cloudflare Email Routing → Worker →
Kurma Mail /api/webhooks/inbound (catch-all ke inbox pemilik API key) →
poll GET {KURMAMAIL_URL}/api/emails/lookup?to=<alamat>&since=<ISO> dengan X-API-Key.
Kredensial: KURMAMAIL_URL, KURMAMAIL_API_KEY (.env). Domain: email.custom_domains / domain.txt.
"""
import random
import string
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from core import config
from core.domains import next_domain
from core.log import warn
from core.mail.base import MailClient
from core.otp import sender_matches


class KurmaMail(MailClient):
    mode = "kurmamail"

    def __init__(self):
        super().__init__()
        self.created_at = datetime.now(timezone.utc)
        self._seen: set[str] = set()

    @staticmethod
    def available() -> bool:
        return bool(config.KURMAMAIL_URL and config.KURMAMAIL_API_KEY and config.CUSTOM_DOMAINS)

    def create(self) -> bool:
        if not self.available():
            return False
        domain = next_domain()
        if not domain:
            return False
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{config.EMAIL_PREFIX}{suffix}@{domain}"
        self.extra = {"domain": domain}
        # toleransi selisih jam server: ambil email sejak 2 menit sebelum mailbox "dibuat"
        self.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        return True

    def _fetch(self) -> list[dict]:
        r = requests.get(
            f"{config.KURMAMAIL_URL}/api/emails/lookup",
            params={"to": self.email, "since": self.created_at.isoformat(), "limit": 10},
            headers={"X-API-Key": config.KURMAMAIL_API_KEY},
            timeout=10,
        )
        if r.status_code == 401:
            warn("Kurma Mail: X-API-Key ditolak (401) — cek KURMAMAIL_API_KEY")
            return []
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("emails") or []

    def poll_message(self, timeout: int) -> Optional[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                for m in self._fetch():
                    mid = str(m.get("id") or m.get("message_id") or "")
                    if mid in self._seen:
                        continue
                    frm, subj = str(m.get("sender_email") or ""), str(m.get("subject") or "")
                    if not sender_matches(frm, subj):
                        continue
                    self._seen.add(mid)
                    return {"id": mid, "from": frm, "subject": subj,
                            "content": str(m.get("body_text") or ""), "html": str(m.get("body_html") or ""),
                            "raw": str(m)}
            except Exception as e:  # noqa: BLE001
                warn(f"Kurma Mail poll error: {e}")
            left = int(deadline - time.time())
            if left > 0:
                print(f"    ⏳ Menunggu email Kurma Mail... ({left}s)", end="\r", flush=True)
                time.sleep(5)
        print()
        return None


def kurmamail_health() -> tuple[bool, str]:
    """GET /api/health Kurma Mail (dipakai diagnostik)."""
    if not config.KURMAMAIL_URL:
        return False, "KURMAMAIL_URL kosong"
    try:
        t0 = time.time()
        r = requests.get(f"{config.KURMAMAIL_URL}/api/health", timeout=8)
        return r.status_code == 200, f"HTTP {r.status_code} ({int((time.time() - t0) * 1000)} ms)"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
