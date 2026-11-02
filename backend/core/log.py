"""core.log — logger konsol berwarna + masking kredensial (diport dari engine sumber)."""
import re

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  X = "\033[0m"; M = "\033[95m"


def ok(msg):   print(f"  {G}✅ {msg}{X}", flush=True)
def err(msg):  print(f"  {R}❌ {msg}{X}", flush=True)
def info(msg): print(f"  {C}ℹ  {msg}{X}", flush=True)
def warn(msg): print(f"  {Y}⚠️  {msg}{X}", flush=True)
def step(msg): print(f"\n  {B}→  {msg}{X}", flush=True)
def hdr(msg):  print(f"\n{M}{B}{msg}{X}", flush=True)


def mask_url(url: str) -> str:
    """Sensor token/kredensial dari URL agar tidak terekspos di log."""
    url = re.sub(r'(token=)([^&]{4})[^&]*', r'\1\2****[REDACTED]', url)
    url = re.sub(r'(password=)([^&]*)', r'\1[REDACTED]', url)
    url = re.sub(r'(secret=)([^&]*)', r'\1[REDACTED]', url)
    return url


def mask_creds(text: str) -> str:
    """Sensor kredensial proxy (user:pass@host) dan token dari teks bebas."""
    text = str(text)
    text = re.sub(r'(https?://|socks[45]h?://)([^:/]+):([^@]+)@', r'\1[REDACTED]:[REDACTED]@', text)
    text = re.sub(r'([a-zA-Z0-9_-]{3,}):([^@:\s]{3,})@([a-zA-Z0-9.-]+:\d+)', r'[REDACTED]:[REDACTED]@\3', text)
    text = re.sub(r'(token=)([^&]{4})[^&]*', r'\1\2****[REDACTED]', text)
    return text


# alias kompatibilitas dengan kode sumber
_mask_url = mask_url
_mask_creds = mask_creds


class Logger:
    """Objek logger ringan yang bisa diberi prefix per akun; dipass ke flow."""

    def __init__(self, prefix: str = ""):
        self.prefix = f"[{prefix}] " if prefix else ""

    def ok(self, m):   ok(self.prefix + str(m))
    def err(self, m):  err(self.prefix + str(m))
    def info(self, m): info(self.prefix + str(m))
    def warn(self, m): warn(self.prefix + str(m))
    def step(self, m): step(self.prefix + str(m))


# ─── Warnai baris RunLogger untuk terminal CLI ───────────────────────────────
_RE_RUNLINE = re.compile(r'^(\[\d\d:\d\d:\d\d\] \[\+\d+\.\d+s\] )(INFO |WARN |ERROR|STAGE)(.*)$')
_LEVEL_COLOR = {"INFO ": C, "WARN ": Y, "ERROR": R, "STAGE": M + B}


def colorize(line: str) -> str:
    """'[HH:MM:SS] [+1.2s] WARN  pesan' → berwarna sesuai level; baris '===' ungu tebal."""
    if line.startswith("==="):
        return f"{M}{B}{line}{X}"
    m = _RE_RUNLINE.match(line)
    if not m:
        return line
    col = _LEVEL_COLOR.get(m.group(2), "")
    return f"{m.group(1)}{col}{m.group(2)}{m.group(3)}{X}"
