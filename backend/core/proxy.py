"""
core.proxy — pool proxy, rotasi round-robin, blacklist sementara, session Croxy,
dan SATU parser proxy → dict Playwright.

Diport dari engine sumber (yang punya 4 parser berbeda; di sini disatukan).
"""
import re
import threading
import time
import uuid
from urllib.parse import urlparse

from core import config
from core.log import info, warn, mask_creds

# ─── Load list ───────────────────────────────────────────────────────────────
_PROXIES: list[str] = list(config.PROXY_LIST)
if not _PROXIES:
    for _pf in config.PROXY_FILES:
        if _pf.exists():
            _PROXIES = [ln.strip() for ln in _pf.read_text().splitlines()
                        if ln.strip() and not ln.strip().startswith("#")]
            if _PROXIES:
                info(f"Loaded {len(_PROXIES)} proxies from {_pf.name}")
                break

_CROXY_BASE = config.CROXY_BASE_PROXY

_counter = 0
_counter_lk = threading.Lock()
_bad: dict[str, float] = {}      # base_proxy → timestamp blacklist
_bad_lk = threading.Lock()

_RE_SESSION = re.compile(r'[_|-]session-[a-zA-Z0-9]+')


def proxy_count() -> int:
    return len(_PROXIES)


def has_proxies() -> bool:
    return bool(_PROXIES or _CROXY_BASE)


def _strip_session(proxy: str) -> str:
    return _RE_SESSION.sub("", proxy)


def _with_session(proxy_url: str) -> str:
    """Tambah session ID unik ke username Croxy → IP baru per akun."""
    try:
        protocol, raw = "http", proxy_url
        if "://" in proxy_url:
            protocol, raw = proxy_url.split("://", 1)
        auth, hostport = raw.rsplit("@", 1)
        user, password = auth.split(":", 1)
        user = _strip_session(user)
        return f"{protocol}://{user}_session-{uuid.uuid4().hex[:8]}:{password}@{hostport}"
    except Exception as e:
        warn(f"Gagal buat session proxy: {e}")
        return proxy_url


def _make_session_proxy(proxy_url: str) -> str:
    """Hanya proxy Croxy yang diberi session ID dinamis."""
    if not proxy_url or "croxy" not in proxy_url.lower():
        return proxy_url
    return _with_session(proxy_url)


def get_next_proxy() -> str:
    """
    Proxy URL untuk 1 akun. Prioritas:
      1. CROXY_BASE_PROXY → session ID baru per akun
      2. PROXY_LIST / proxy.txt → round-robin, skip yang di-blacklist (cooldown PROXY_BAD_COOLDOWN)
         jika semua bad → pakai yang paling lama di-blacklist
      3. '' → tanpa proxy
    """
    if _CROXY_BASE:
        return _with_session(_CROXY_BASE)

    global _counter
    if not _PROXIES:
        return ""

    now = time.time()
    with _bad_lk:
        for p in [p for p, t in _bad.items() if now - t > config.PROXY_BAD_COOLDOWN]:
            _bad.pop(p, None)
        active = [p for p in _PROXIES if p not in _bad]
        if not active:
            if len(_PROXIES) == 1:
                return ""
            oldest = sorted(_bad.items(), key=lambda x: x[1])
            if oldest:
                _bad.pop(oldest[0][0], None)
                active = [oldest[0][0]]
            else:
                active = list(_PROXIES)

    with _counter_lk:
        _counter += 1
        idx = _counter % len(active)
    return _make_session_proxy(active[idx])


def blacklist_proxy(proxy: str) -> None:
    """Tandai proxy bermasalah (base, tanpa session ID)."""
    if not proxy:
        return
    base = _strip_session(proxy)
    with _bad_lk:
        _bad[base] = time.time()
    warn(f"Proxy diblacklist sementara: {mask_creds(base[:60])}")


def is_blacklisted(proxy: str) -> bool:
    if not proxy:
        return False
    with _bad_lk:
        return _strip_session(proxy) in _bad


def bad_proxy_count() -> int:
    with _bad_lk:
        return len(_bad)


# ─── Parser tunggal ──────────────────────────────────────────────────────────
_SCHEMES = ("http://", "https://", "socks5://", "socks5h://", "socks4://")


def parse_proxy(raw: str) -> dict | None:
    """
    Terima semua format umum dan kembalikan dict Playwright
    {"server": "scheme://host:port", "username"?: ..., "password"?: ...}.

      host:port:user:pass
      user:pass:host:port
      user:pass@host:port
      scheme://user:pass@host:port
      scheme://host:port
      host:port
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return None

    if raw.lower().startswith(_SCHEMES):
        p = urlparse(raw)
        if not p.hostname:
            return None
        server = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")
        d = {"server": server}
        if p.username: d["username"] = p.username
        if p.password: d["password"] = p.password
        return d

    if "@" in raw:
        auth, hostport = raw.rsplit("@", 1)
        d = {"server": f"http://{hostport}"}
        if ":" in auth:
            user, pw = auth.split(":", 1)
            d["username"], d["password"] = user, pw
        return d

    parts = raw.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            host, port, user, pw = parts
        else:
            user, pw, host, port = parts
        return {"server": f"http://{host}:{port}", "username": user, "password": pw}
    if len(parts) == 2:
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    return None
