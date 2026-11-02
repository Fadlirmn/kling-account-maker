"""
core.otp — ekstraksi OTP / link verifikasi dari email, dan filter pengirim.

Urutan extract_otp (frasa khas site dari env OTP_PHRASES):
  1. frasa khusus site (OTP_PHRASES) di sekitar N digit
  2. kata kunci generik (code/kode/verification/otp/pin) + N digit
  3. N digit pertama (fallback terakhir — rawan nyangkut angka CSS, makanya terakhir)
"""
import re
from typing import Optional

from core import config

_RE_TAG = re.compile(r'<[^>]+>')
_RE_URL = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)


def _to_text(email_data) -> str:
    if not email_data:
        return ""
    if isinstance(email_data, str):
        raw = email_data
    else:
        raw = " ".join(str(email_data.get(k, "")) for k in ("subject", "content", "html", "raw"))
    return _RE_TAG.sub(" ", raw)


def extract_otp(email_data, phrases: Optional[list[str]] = None, length: int = None) -> Optional[str]:
    clean = _to_text(email_data)
    if not clean:
        return None
    n = length or config.OTP_LENGTH
    digits = rf'\b(\d{{{n}}})\b'
    phrases = config.OTP_PHRASES if phrases is None else phrases

    patterns = []
    for ph in phrases:
        ph_re = re.escape(ph.strip()).replace(r'\ ', r'\s*')
        patterns.append(rf'{digits}\s*(?:{ph_re})')
        patterns.append(rf'(?:{ph_re})[^\n]{{0,60}}?{digits}')
    patterns.append(rf'(?:code|kode|verifikasi|verification|otp|pin)[^\n]{{0,50}}?{digits}')

    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            return m.group(1)
    m = re.search(digits, clean)
    return m.group(1) if m else None


def extract_link(email_data, url_patterns: Optional[list[str]] = None) -> Optional[str]:
    """Link verifikasi: coba pattern khusus (regex) dulu, lalu URL http pertama."""
    if not email_data:
        return None
    raw = email_data if isinstance(email_data, str) else " ".join(
        str(email_data.get(k, "")) for k in ("content", "html", "raw"))
    raw = raw.replace("&amp;amp;", "&").replace("&amp;", "&")
    for pat in url_patterns or []:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            return m.group(0)
    m = _RE_URL.search(raw)
    return m.group(0) if m else None


def sender_matches(frm: str, subj: str, keywords: Optional[list[str]] = None) -> bool:
    """True jika from/subject mengandung salah satu kata kunci MAIL_SENDER_FILTER. Kosong = semua lolos."""
    kws = config.MAIL_SENDER_FILTER if keywords is None else keywords
    if not kws:
        return True
    blob = f"{frm} {subj}".lower()
    return any(k in blob for k in kws)
