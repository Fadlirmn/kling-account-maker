"""core.mail.base — interface seragam semua provider email."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from core import config
from core.otp import extract_otp, extract_link


class MailClient(ABC):
    """
    Satu mailbox sementara.

    Siklus: client = Provider(); ok = client.create()  → client.email terisi
            otp = client.poll_otp(timeout)              → blocking (sync), panggil via asyncio.to_thread
    """
    mode: str = ""          # 'webhook' | 'local_tempmail' | '1secmail' | 'mailtm' | 'gptmail'
    email: str = ""
    extra: dict             # data provider (login/domain/token/...), disimpan ke result

    def __init__(self):
        self.extra = {}

    @abstractmethod
    def create(self) -> bool:
        """Buat mailbox; isi self.email. False jika provider gagal/tidak tersedia."""

    @abstractmethod
    def poll_message(self, timeout: int) -> Optional[dict]:
        """
        Tunggu 1 email relevan (sudah difilter sender). Return dict
        {"id","from","subject","content","html","raw"} atau None saat timeout.
        Provider webhook yang hanya mengembalikan OTP boleh override poll_otp saja
        dan mengembalikan None di sini.
        """

    def poll_otp(self, timeout: int = None) -> str:
        """Default: poll_message → extract_otp. Return '' jika gagal."""
        timeout = timeout or config.OTP_TIMEOUT
        deadline = time.time() + timeout
        while time.time() < deadline:
            left = max(1, int(deadline - time.time()))
            msg = self.poll_message(min(left, 20))
            if msg:
                otp = extract_otp(msg)
                if otp:
                    return otp
        return ""

    def poll_link(self, timeout: int = None, url_patterns: list[str] = None) -> str:
        """Tunggu email berisi link verifikasi. Return '' jika gagal."""
        timeout = timeout or config.OTP_TIMEOUT
        deadline = time.time() + timeout
        while time.time() < deadline:
            left = max(1, int(deadline - time.time()))
            msg = self.poll_message(min(left, 20))
            if msg:
                link = extract_link(msg, url_patterns)
                if link:
                    return link
        return ""

    @property
    def domain(self) -> str:
        return self.email.split("@", 1)[-1] if "@" in self.email else ""

    def __repr__(self):
        return f"<{self.__class__.__name__} mode={self.mode} email={self.email}>"


def _countdown(left: int, label: str = "") -> None:
    print(f"    ⏳ {label}{left}s...", end="\r", flush=True)
