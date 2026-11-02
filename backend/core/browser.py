"""
core.browser — launch Camoufox anti-detect, semaphore concurrency, request routing,
retry GeoIP, klasifikasi error, debug screenshot.

Diport dari engine sumber.
Perubahan: env Firefox dipindah ke bootstrap; tmp dir tak terpakai dibuang; sysctl/shm hanya root+Docker;
pref popup-blocker (hanya perlu untuk flow dengan popup OAuth) jadi opsi `allow_popups`.
"""
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from camoufox.async_api import AsyncCamoufox

from core import config
from core.log import info, warn, mask_creds
from core.proxy import parse_proxy, blacklist_proxy

_browser_semaphore = threading.Semaphore(max(1, config.BROWSER_CONCURRENCY))
_concurrency = max(1, config.BROWSER_CONCURRENCY)


def set_concurrency(n: int) -> None:
    """Ganti batas browser paralel (dipanggil runner sebelum batch; aman saat tidak ada browser aktif)."""
    global _browser_semaphore, _concurrency
    n = max(1, int(n))
    if n != _concurrency:
        _browser_semaphore = threading.Semaphore(n)
        _concurrency = n

_LAUNCH_PROXY_KWS = ["failed to connect to proxy", "invalidproxy", "proxyerror",
                     "max retries exceeded", "tunnel connection failed", "failed to get ip address"]
_PROXY_ERR_KWS = ["econnrefused", "econnreset", "net::err_proxy", "proxy authentication", "407",
                  "tunnel", "failed to get ip address", "unknown_proxy_host", "ns_error",
                  "failed to connect to proxy", "invalidproxy", "proxyerror", "max retries exceeded", "timeout"]
_BROWSER_CRASH_KWS = ["connection closed", "browser.close", "driver", "cannot read properties", "node.js"]


class BrowserBusy(Exception):
    """Semaphore browser penuh > timeout."""


class ProxyError(Exception):
    """Proxy mati saat launch (sudah di-blacklist)."""


def is_xvfb() -> bool:
    return bool(os.environ.get("DISPLAY"))


def _tune_system_once() -> None:
    """sysctl userns + /dev/shm 512M — hanya root di dalam Docker; gagal diabaikan."""
    if getattr(_tune_system_once, "_done", False):
        return
    _tune_system_once._done = True
    try:
        if os.geteuid() != 0 or not os.path.exists("/.dockerenv"):
            return
    except AttributeError:
        return
    for cmd in (["sysctl", "-w", "kernel.unprivileged_userns_clone=1"],
                ["mount", "-o", "remount,size=512M", "/dev/shm"]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except Exception:
            pass


def build_launch_kwargs(proxy_url: str = "", headless: Optional[bool] = None,
                        allow_popups: bool = False, geoip: bool = True) -> dict:
    """
    headless None → otomatis: headful jika DISPLAY (Xvfb) ada, else headless.
    geoip=True → timezone/locale/geo dari IP proxy (butuh MMDB).
    """
    if headless is None:
        headless = not is_xvfb()
    if headless:
        os.environ["MOZ_HEADLESS"] = "1"
    else:
        os.environ.pop("MOZ_HEADLESS", None)

    prefs = {
        "security.sandbox.content.level": 0,
        "browser.cache.disk.enable": False,
        "browser.cache.memory.enable": False,
        "browser.cache.offline.enable": False,
        "browser.cache.memory.capacity": 32768,
        "browser.sessionstore.interval": 3600000,
        "dom.storage.enabled": True,
        "privacy.partition.network_state.ocsp_cache": True,
        "network.cookie.cookieBehavior": 0,
        "dom.ipc.processCount": 1,
        "dom.ipc.processCount.web": 1,
    }
    if allow_popups:
        prefs.update({
            "dom.disable_open_during_load": False,
            "dom.block_multiple_popups": False,
            "dom.popup_allowed_events": "change click dblclick auxclick mouseup pointerup notificationclick reset submit touchend contextmenu",
            "privacy.popups.firstTime": False,
            "browser.popups.showPopupBlocker": False,
            "browser.link.open_newwindow": 3,
            "browser.link.open_newwindow.restriction": 0,
        })

    kw = dict(headless=headless, geoip=geoip, humanize=True, os="windows", firefox_user_prefs=prefs)
    if proxy_url:
        pd = parse_proxy(proxy_url)
        if pd:
            kw["proxy"] = pd
        else:
            warn(f"Gagal parse proxy '{mask_creds(proxy_url)}' — pakai server mentah")
            kw["proxy"] = {"server": proxy_url}
    return kw


def classify_error(exc: BaseException, proxy_url: str = "") -> str:
    """'proxy' | 'browser' | 'other' berdasar keyword pesan error."""
    s = str(exc).lower()
    is_browser = any(k in s for k in _BROWSER_CRASH_KWS)
    is_proxy = bool(proxy_url) and any(k in s for k in _PROXY_ERR_KWS)
    if is_browser:
        return "browser"
    if is_proxy:
        return "proxy"
    return "other"


_BLOCKED_STYLE_DOMAINS = ["fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "fast.fonts.net",
                          "cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"]
_TRACKERS = ["google-analytics", "googletagmanager", "doubleclick", "facebook.net", "facebook.com/tr", "sentry.io",
             "hotjar", "mixpanel", "amplitude", "optimizely", "branch.io", "datadoghq", "inspectlet", "clarity.ms",
             "adnxs", "smartadserver", "criteo", "amazon-adsystem", "telemetry", "/log/", "log-delivery",
             "segment.io", "segment.com", "newrelic", "fullstory", "intercom.io", "intercomcdn", "heap.io", "logrocket"]


async def setup_context_routing(ctx) -> None:
    """Hemat bandwidth proxy: blokir image/media/font, CSS CDN, tracker. ROUTING_ALLOWLIST tidak pernah diblokir."""
    allow = config.ROUTING_ALLOWLIST

    async def intercept(route, request):
        url = request.url.lower()
        if allow and any(a in url for a in allow):
            await route.continue_(); return
        rt = request.resource_type
        if rt in ("image", "media", "font"):
            await route.abort(); return
        if rt == "stylesheet" and any(d in url for d in _BLOCKED_STYLE_DOMAINS):
            await route.abort(); return
        if any(t in url for t in _TRACKERS):
            await route.abort(); return
        await route.continue_()

    await ctx.route("**/*", intercept)


async def save_debug_screenshot(page, email: str, step_name: str) -> Optional[Path]:
    if not config.DEBUG_SCREENSHOTS:
        return None
    try:
        config.RESULT_DIR.mkdir(parents=True, exist_ok=True)
        clean = str(email).replace("@", "_").replace(".", "_")
        path = config.RESULT_DIR / f"{clean}_{step_name}.png"
        await page.screenshot(path=str(path))
        info(f"Debug screenshot: {path.name}")
        return path
    except Exception as e:
        warn(f"Gagal simpan screenshot: {e}")
        return None


class BrowserSession:
    """
    async with BrowserSession(proxy_url) as (browser, ctx, page): ...

    - Acquire semaphore (timeout 300s → BrowserBusy)
    - Launch Camoufox; jika error proxy saat launch & geoip aktif → retry geoip=False
      (proxy mungkin blokir api.ipify tapi bisa buka target); masih gagal → blacklist + ProxyError
    - Context: locale BROWSER_LOCALE, viewport None, ignore_https_errors, routing hemat bandwidth
    """

    def __init__(self, proxy_url: str = "", allow_popups: bool = False, headless: Optional[bool] = None):
        self.proxy_url = proxy_url
        self.allow_popups = allow_popups
        self.headless = headless
        self._cm = None
        self._acquired = False

    async def _open(self, kw):
        self._cm = AsyncCamoufox(**kw)
        browser = await self._cm.__aenter__()
        ctx = await browser.new_context(locale=config.BROWSER_LOCALE, viewport=None, ignore_https_errors=True)
        ctx.on("page", lambda p: p.on("pageerror", lambda _e: None))
        await setup_context_routing(ctx)
        page = await ctx.new_page()
        page.on("pageerror", lambda _e: None)
        return browser, ctx, page

    async def __aenter__(self):
        _tune_system_once()
        self._acquired = _browser_semaphore.acquire(blocking=True, timeout=300)
        if not self._acquired:
            raise BrowserBusy("browser_semaphore_timeout")
        kw = build_launch_kwargs(self.proxy_url, headless=self.headless, allow_popups=self.allow_popups)
        info(f"Launch browser | Proxy: {mask_creds(self.proxy_url) if self.proxy_url else 'None (Direct)'} | headless={kw['headless']}")
        try:
            return await self._open(kw)
        except Exception as e:
            await self._close_cm(type(e), e, None)
            s = str(e).lower()
            if self.proxy_url and kw.get("geoip") and any(k in s for k in _LAUNCH_PROXY_KWS):
                warn(f"GeoIP/proxy check gagal ({mask_creds(str(e)[:100])}) — retry tanpa GeoIP...")
                kw["geoip"] = False
                try:
                    return await self._open(kw)
                except Exception as e2:
                    await self._close_cm(type(e2), e2, None)
                    blacklist_proxy(self.proxy_url)
                    self._release()
                    raise ProxyError(str(e2)) from e2
            self._release()
            raise

    async def _close_cm(self, et, ev, tb):
        if self._cm is not None:
            try:
                await self._cm.__aexit__(et, ev, tb)
            except Exception:
                pass
            self._cm = None

    def _release(self):
        if self._acquired:
            _browser_semaphore.release()
            self._acquired = False

    async def __aexit__(self, et, ev, tb):
        await self._close_cm(et, ev, tb)
        self._release()
        return False
