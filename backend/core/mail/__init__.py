"""
core.mail — factory + fallback chain provider email.

Urutan (diport dari engine sumber):
  preferred (EMAIL_PROVIDER) → webhook → local_tempmail → 1secmail → mailtm → gptmail (jika ALLOW_GPTMAIL_FALLBACK)
Provider yang gagal create() dicatat di `disabled` (per thread/slot) agar attempt berikut melompatinya.
"""
from typing import Optional

from core import config
from core.log import info, warn
from core.mail.base import MailClient
from core.mail.webhook import WebhookMail
from core.mail.local_tempmail import LocalTempMail
from core.mail.secmail import SecMail
from core.mail.mailtm import MailTm
from core.mail.gptmail import GptMail

PROVIDERS: dict[str, type[MailClient]] = {
    "webhook": WebhookMail,
    "local_tempmail": LocalTempMail,
    "1secmail": SecMail,
    "mailtm": MailTm,
    "gptmail": GptMail,
}

_DEFAULT_CHAIN = ["webhook", "local_tempmail", "1secmail", "mailtm", "gptmail"]


def provider_chain(preferred: Optional[str] = None) -> list[str]:
    pref = (preferred or config.EMAIL_PROVIDER).lower()
    chain = [pref] + [p for p in _DEFAULT_CHAIN if p != pref]
    if not config.ALLOW_GPTMAIL_FALLBACK and pref != "gptmail":
        chain = [p for p in chain if p != "gptmail"]
    # provider yang butuh konfigurasi: skip kalau tidak tersedia
    if not WebhookMail.available():
        chain = [p for p in chain if p != "webhook"]
    if not LocalTempMail.available():
        chain = [p for p in chain if p != "local_tempmail"]
    return chain


def make_mail_client(preferred: Optional[str] = None, disabled: Optional[set] = None) -> Optional[MailClient]:
    """
    Coba provider berurutan sampai ada yang berhasil create().
    `disabled` (set, mutable) diisi nama provider yang gagal agar panggilan berikut melompatinya.
    Return None jika semua gagal.
    """
    disabled = disabled if disabled is not None else set()
    for name in provider_chain(preferred):
        if name in disabled:
            continue
        cls = PROVIDERS.get(name)
        if not cls:
            continue
        client = cls()
        try:
            if client.create() and client.email:
                info(f"Email provider: {name} → {client.email}")
                return client
        except Exception as e:
            warn(f"Provider {name} error: {e}")
        disabled.add(name)
        warn(f"Provider {name} tidak tersedia, coba berikutnya...")
    return None


__all__ = ["MailClient", "make_mail_client", "provider_chain", "PROVIDERS",
           "WebhookMail", "LocalTempMail", "SecMail", "MailTm", "GptMail"]
