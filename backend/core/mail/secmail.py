"""core.mail.secmail — 1secmail (https://www.1secmail.com/api/v1/). Diport dari engine sumber."""
import random
import string
import time
from typing import Optional

import requests

from core.log import warn
from core.mail.base import MailClient, _countdown
from core.otp import sender_matches

API = "https://www.1secmail.com/api/v1/"
DOMAINS = ["1secmail.com", "1secmail.org", "1secmail.net", "esiix.com", "xojxe.com", "yoggm.com", "wwjmp.com"]


class SecMail(MailClient):
    mode = "1secmail"

    def __init__(self):
        super().__init__()
        self.login = self.dom = ""

    def create(self) -> bool:
        try:
            r = requests.get(API, params={"action": "genRandomMailbox", "count": 1}, timeout=10)
            if r.status_code == 200:
                self.email = r.json()[0]
        except Exception as e:
            warn(f"1secmail generate: {e}")
        if not self.email:
            login = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            self.email = f"{login}@{random.choice(DOMAINS)}"
        self.login, self.dom = self.email.split("@", 1)
        self.extra = {"login": self.login, "domain": self.dom}
        return True

    def poll_message(self, timeout: int) -> Optional[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            left = int(deadline - time.time())
            try:
                r = requests.get(API, params={"action": "getMessages", "login": self.login, "domain": self.dom}, timeout=10)
                if r.status_code == 200:
                    for msg in r.json():
                        frm, subj = str(msg.get("from", "")), str(msg.get("subject", ""))
                        if not sender_matches(frm, subj):
                            continue
                        mid = msg.get("id")
                        if not mid:
                            continue
                        r2 = requests.get(API, params={"action": "readMessage", "login": self.login,
                                                       "domain": self.dom, "id": mid}, timeout=10)
                        if r2.status_code == 200:
                            d2 = r2.json()
                            print()
                            return {"id": mid, "from": frm, "subject": subj,
                                    "content": d2.get("textBody", ""), "html": d2.get("htmlBody", ""), "raw": str(d2)}
            except Exception:
                pass
            _countdown(left)
            time.sleep(5)
        print()
        return None
