"""core.mail.mailtm — mail.tm (https://api.mail.tm). Diport dari engine sumber."""
import random
import string
import time
from typing import Optional

import requests

from core.log import warn
from core.mail.base import MailClient, _countdown
from core.otp import sender_matches

API = "https://api.mail.tm"


class MailTm(MailClient):
    mode = "mailtm"

    def __init__(self):
        super().__init__()
        self.token = ""

    def create(self) -> bool:
        try:
            r = requests.get(f"{API}/domains", timeout=10)
            if r.status_code != 200:
                return False
            domains = r.json().get("hydra:member", [])
            if not domains:
                return False
            domain = domains[0]["domain"]
            password = "".join(random.choices(string.ascii_letters + string.digits, k=16))
            login = "".join(random.choices(string.ascii_lowercase, k=10))
            email = f"{login}@{domain}"
            r2 = requests.post(f"{API}/accounts", json={"address": email, "password": password}, timeout=10)
            if r2.status_code not in (200, 201):
                return False
            r3 = requests.post(f"{API}/token", json={"address": email, "password": password}, timeout=10)
            if r3.status_code != 200:
                return False
            self.token = r3.json().get("token", "")
            if not self.token:
                return False
            self.email = email
            self.extra = {"token": self.token, "account_id": r2.json().get("id", "")}
            return True
        except Exception as e:
            warn(f"mail.tm create: {e}")
            return False

    def poll_message(self, timeout: int) -> Optional[dict]:
        hdrs = {"Authorization": f"Bearer {self.token}"}
        deadline = time.time() + timeout
        while time.time() < deadline:
            left = int(deadline - time.time())
            try:
                r = requests.get(f"{API}/messages", headers=hdrs, timeout=10)
                if r.status_code == 200:
                    for msg in r.json().get("hydra:member", []):
                        frm = str((msg.get("from") or {}).get("address", ""))
                        subj = str(msg.get("subject", ""))
                        if not sender_matches(frm, subj):
                            continue
                        mid = msg.get("id", "")
                        if not mid:
                            continue
                        r2 = requests.get(f"{API}/messages/{mid}", headers=hdrs, timeout=10)
                        if r2.status_code == 200:
                            d2 = r2.json()
                            html = d2.get("html")
                            print()
                            return {"id": mid, "from": frm, "subject": subj, "content": d2.get("text", ""),
                                    "html": html[0] if isinstance(html, list) and html else (html or ""), "raw": str(d2)}
            except Exception:
                pass
            _countdown(left)
            time.sleep(5)
        print()
        return None
