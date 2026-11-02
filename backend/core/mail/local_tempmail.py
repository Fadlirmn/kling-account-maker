"""
core.mail.local_tempmail — Go TempMail self-hosted (REST + tulis langsung ke SQLite mailboxes).

Diport dari engine sumber. Semua path/secret dari env (tidak ada hardcode).
"""
import random
import sqlite3
import string
import time
from typing import Optional

import requests

from core import config
from core.domains import next_domain
from core.log import info, warn
from core.mail.base import MailClient
from core.otp import extract_otp, sender_matches


class LocalTempMail(MailClient):
    mode = "local_tempmail"

    def __init__(self):
        super().__init__()
        self.token = ""

    @staticmethod
    def available() -> bool:
        return bool(config.TEMPMAIL_API_URL)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _get_token(self) -> str:
        try:
            r = requests.post(f"{config.TEMPMAIL_API_URL}/api/auth", json={"secret": config.TEMPMAIL_SECRET}, timeout=5)
            if r.status_code == 200:
                return r.json().get("token", "")
        except Exception as e:
            warn(f"Gagal token TempMail ({config.TEMPMAIL_API_URL}): {e}")
        return ""

    @staticmethod
    def _load_domains() -> list[str]:
        try:
            with open(config.TEMPMAIL_DOMAIN_FILE, "r", encoding="utf-8") as f:
                doms = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
            if doms:
                return doms
        except Exception:
            pass
        return list(config.CUSTOM_DOMAINS)

    def _get_prefix(self) -> str:
        try:
            r = requests.get(f"{config.TEMPMAIL_API_URL}/api/mailboxes", headers=self._headers(), timeout=5)
            if r.status_code == 200 and r.json():
                latest = r.json()[0].get("address", "")
                if "_" in latest:
                    return latest.split("_")[0]
        except Exception:
            pass
        return config.EMAIL_PREFIX.rstrip("_") or "mail"

    def _register_mailbox(self, email: str) -> None:
        try:
            conn = sqlite3.connect(config.TEMPMAIL_DB_PATH)
            conn.execute("INSERT OR IGNORE INTO mailboxes (address, active, created) VALUES (?, 1, datetime('now'))", (email,))
            conn.commit()
            conn.close()
            info(f"Mailbox {email} didaftarkan ke SQLite TempMail")
        except Exception as e:
            warn(f"Gagal daftar mailbox di SQLite TempMail ({config.TEMPMAIL_DB_PATH}): {e}")

    # ── MailClient ──────────────────────────────────────────────────────────
    def create(self) -> bool:
        if not self.available():
            return False
        self.token = self._get_token()
        if not self.token:
            return False
        domains = self._load_domains()
        if not domains:
            return False
        domain = next_domain()
        if not domain or domain not in domains:
            domain = random.choice(domains)
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.email = f"{self._get_prefix()}_{rand}@{domain}"
        self._register_mailbox(self.email)
        self.extra = {"domain": domain}
        return True

    def _fetch(self) -> list[dict]:
        r = requests.get(f"{config.TEMPMAIL_API_URL}/api/emails", params={"mailbox": self.email},
                         headers=self._headers(), timeout=5)
        return r.json() if r.status_code == 200 and r.json() else []

    def poll_message(self, timeout: int) -> Optional[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                for m in self._fetch():
                    frm, subj = str(m.get("from", "")), str(m.get("subject", ""))
                    if sender_matches(frm, subj):
                        return {"id": m.get("id", ""), "from": frm, "subject": subj,
                                "content": str(m.get("body", "")), "html": str(m.get("html", "")),
                                "raw": str(m), "otp": str(m.get("otp", "")).strip()}
            except Exception:
                pass
            time.sleep(5)
        return None

    def poll_otp(self, timeout: int = None) -> str:
        """Server TempMail sudah mengekstrak field `otp`; pakai itu dulu, lalu regex."""
        timeout = timeout or config.OTP_TIMEOUT
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.poll_message(min(20, max(1, int(deadline - time.time()))))
            if msg:
                otp = msg.get("otp") or extract_otp(msg)
                if otp:
                    return otp
        return ""
