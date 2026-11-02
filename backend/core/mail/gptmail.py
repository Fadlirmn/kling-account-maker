"""core.mail.gptmail — GPTMail (mail.chatgpt.org.uk), fallback terakhir. Diport dari engine sumber."""
import json
import re
import time
from typing import Optional

import requests

from core.log import err
from core.mail.base import MailClient, _countdown
from core.otp import sender_matches

BASE = "https://mail.chatgpt.org.uk"


class GptMail(MailClient):
    mode = "gptmail"

    def __init__(self):
        super().__init__()
        self.sess: Optional[requests.Session] = None
        self.mb_token = ""

    def create(self) -> bool:
        try:
            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            r = s.get(BASE, timeout=15)
            m = re.search(r'window\.__BROWSER_AUTH\s*=\s*(\{.*?\});', r.text)
            if not m:
                return False
            tok = json.loads(m.group(1)).get("token", "")
            if not tok:
                return False
            r2 = s.get(f"{BASE}/api/generate-email", headers={"X-Inbox-Token": tok, "Accept": "application/json"}, timeout=10)
            if r2.status_code != 200 or not r2.json().get("success"):
                return False
            data = r2.json()
            self.email = data["data"]["email"]
            self.mb_token = data.get("auth", {}).get("token", tok)
            self.sess = s
            self.extra = {"mb_token": self.mb_token}
            return True
        except Exception as e:
            err(f"GPTMail init: {e}")
            return False

    def poll_message(self, timeout: int) -> Optional[dict]:
        hdrs = {"X-Inbox-Token": self.mb_token, "Accept": "application/json"}
        deadline = time.time() + timeout
        while time.time() < deadline:
            left = int(deadline - time.time())
            try:
                r = self.sess.get(f"{BASE}/api/emails", headers=hdrs, params={"email": self.email}, timeout=10)
                if r.status_code == 429:
                    time.sleep(5); continue
                if r.status_code != 200:
                    time.sleep(3); continue
                for msg in r.json().get("data", {}).get("emails", []):
                    frm, subj = str(msg.get("from_address", "")), str(msg.get("subject", ""))
                    if not sender_matches(frm, subj):
                        continue
                    mid = msg.get("id", "")
                    if mid:
                        r2 = self.sess.get(f"{BASE}/api/email/{mid}", headers=hdrs, timeout=10)
                        d2 = r2.json().get("data", {})
                        print()
                        return {"id": mid, "from": frm, "subject": subj, "content": d2.get("content", ""),
                                "html": d2.get("html_content", ""), "raw": str(d2)}
                    print()
                    return {"id": "", "from": frm, "subject": subj, "content": str(msg), "html": "", "raw": str(msg)}
            except Exception:
                pass
            _countdown(left)
            time.sleep(5)
        print()
        return None
