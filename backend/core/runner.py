"""
core.runner — orkestrasi satu run (batch) pembuatan akun.

  run_id = run_batch(engine, trigger="manual", count=5, workers=2)

Alur: settings (DB) → proxy → browser (BrowserSession) → flow site → klasifikasi error →
retry dengan fallback provider → simpan hasil (repo.upsert_account + file) → finish_run.
Flow site (sites/<SITE_NAME>/flow.py) hanya mengisi langkah di halaman; runner yang
memutuskan blacklist/retry. Log per run lewat RunLogger (kolom runs.log + LOG_DIR/run_<id>.log).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from core import config
from core import proxy as proxy_mod
from core import domains
from core import browser as browser_mod
from core.browser import BrowserSession, BrowserBusy, ProxyError, classify_error
from core.log import mask_creds, Logger
from core.mail import make_mail_client, MailClient, provider_chain
from core.ram import get_safe_workers
from core.results import save_result, db_insert_account
from runlog import RunLogger, describe_exc


# ─── Hasil ───────────────────────────────────────────────────────────────────
@dataclass
class AccountResult:
    email: str
    password: str = ""
    success: bool = False
    user_id: str = ""
    otp: str = ""
    cookies: list = field(default_factory=list)
    proxy: str = ""
    email_mode: str = ""
    status: str = "failed"          # standby | failed
    error: str = ""                 # kode machine-readable (lihat kontrak di bawah)
    attempts: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_db(self) -> dict:
        d = self.to_dict()
        d["cookies"] = json.dumps(self.cookies) if isinstance(self.cookies, list) else self.cookies
        return d


# ─── Sinyal dari flow ke runner ──────────────────────────────────────────────
class FlowError(Exception):
    """Base. Flow site melempar subclass ini; runner yang memutuskan retry/blacklist."""
    code = "flow_error"


class DomainBlocked(FlowError):
    """Site menolak domain email → domain di-ban (memori + DB), retry dengan email lain."""
    def __init__(self, domain: str):
        super().__init__(f"DOMAIN_BLOCKED:{domain}")
        self.domain = domain
        self.code = f"DOMAIN_BLOCKED:{domain}"


class ProxyFlagged(FlowError):
    """IP/proxy di-flag (redirect home, Cloudflare, captcha) → blacklist proxy, sleep, retry."""
    def __init__(self, reason: str = ""):
        self.reason = reason
        self.code = "PROXY_FLAGGED_CLOUDFLARE" if "cloudflare" in reason.lower() else "PROXY_FLAGGED"
        super().__init__(self.code)


class OtpTimeout(FlowError):
    def __init__(self, msg: str = "otp timeout"):
        super().__init__(msg)
        self.code = msg


class FormNotFound(FlowError):
    """Elemen wajib tidak ditemukan ('email input', 'otp form', ...)."""
    def __init__(self, what: str):
        super().__init__(f"{what} not found")
        self.what = what
        self.code = f"{what} not found"


NON_RETRYABLE = {"NOT_IMPLEMENTED", "browser_semaphore_timeout", "max_attempts_exceeded",
                 "no_mail_provider", "aborted"}
FATAL_ERRORS = {"NOT_IMPLEMENTED"}       # satu slot kena → seluruh run dihentikan


def load_flow():
    """sites.<SITE_NAME>.flow — dipisah agar site bisa diganti tanpa ubah runner."""
    return importlib.import_module(f"sites.{config.SITE_NAME}.flow")


def flow_implemented() -> bool:
    try:
        return not getattr(load_flow(), "IS_STUB", False)
    except Exception:  # noqa: BLE001
        return False


# ─── Satu percobaan ──────────────────────────────────────────────────────────
async def create_one(mail_client: MailClient, password: Optional[str] = None,
                     proxy_url: Optional[str] = None, log=None) -> AccountResult:
    """
    Satu attempt penuh untuk satu email: launch browser → flow.create_account → result.
    Tidak pernah raise; semua error jadi result.error.
    """
    log = log or Logger(mail_client.email.split("@")[0][:14])
    password = password if password is not None else config.KLING_DEFAULT_PASSWORD
    proxy_url = proxy_mod.get_next_proxy() if proxy_url is None else proxy_url
    res = AccountResult(email=mail_client.email, password=password, proxy=proxy_url, email_mode=mail_client.mode)

    if not proxy_url and proxy_mod.has_proxies():
        log.warn("Semua proxy ter-blacklist — mencoba tanpa proxy (IP server langsung)")

    flow = load_flow()
    try:
        async with BrowserSession(proxy_url, allow_popups=getattr(flow, "ALLOW_POPUPS", False)) as (browser, ctx, page):
            out = await flow.create_account(page, ctx, mail_client.email, password, mail_client, log)
            if isinstance(out, AccountResult):
                out.proxy, out.email_mode = proxy_url, mail_client.mode
                if out.success and out.status == "failed":
                    out.status = "standby"
                return out
            res.error = "flow returned invalid result"
            return res

    except NotImplementedError as e:
        res.error = "NOT_IMPLEMENTED"
        log.err(f"Flow {config.SITE_NAME} belum diimplementasi: {e}")
    except BrowserBusy:
        res.error = "browser_semaphore_timeout"
        log.warn("Browser semaphore timeout — terlalu banyak browser concurrent")
    except ProxyError as e:
        res.error = f"exception: proxy: {mask_creds(str(e)[:100])}"
    except DomainBlocked as e:
        res.error = e.code
    except ProxyFlagged as e:
        res.error = e.code
        proxy_mod.blacklist_proxy(proxy_url)
    except FlowError as e:
        res.error = e.code
    except Exception as e:  # noqa: BLE001
        kind = classify_error(e, proxy_url)
        if kind == "proxy" and not proxy_mod.is_blacklisted(proxy_url):
            proxy_mod.blacklist_proxy(proxy_url)
        log.err(f"Exception saat membuat akun: {mask_creds(describe_exc(e)[:200])}")
        res.error = f"exception: {mask_creds(str(e)[:120])}"
    return res


# ─── Satu slot dengan retry ──────────────────────────────────────────────────
def _decide(err_val: str, mail_client: Optional[MailClient]) -> tuple[bool, float]:
    """(retry?, sleep_detik). Tabel keputusan retry."""
    if not err_val or err_val in NON_RETRYABLE:
        return False, 0
    if err_val.startswith("DOMAIN_BLOCKED:"):
        dom = err_val.split(":", 1)[1]
        domains.blacklist_domain(dom)
        domains.ban_domain_in_db(dom)
        return True, 0
    if err_val.startswith("PROXY_FLAGGED"):
        return True, 15
    if err_val.startswith("email timeout") or err_val in ("otp extract failed", "otp timeout"):
        if mail_client and mail_client.mode in ("webhook", "local_tempmail") and mail_client.domain:
            domains.blacklist_domain(mail_client.domain)
        return True, 5
    if err_val.endswith(" not found") or err_val.startswith("exception:"):
        return True, 5
    return False, 0


def run_slot(slot_idx: int, preferred_provider: Optional[str], max_attempts: int,
             stop_event: Optional[threading.Event], rl: RunLogger) -> AccountResult:
    """Sync; dijalankan di thread pool. Event loop asyncio sendiri per thread."""
    slog = rl.child(f"slot {slot_idx}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    disabled: set[str] = set()
    last: Optional[AccountResult] = None
    try:
        for attempt in range(1, max_attempts + 1):
            if stop_event is not None and stop_event.is_set():
                return last or AccountResult(email="", error="aborted", attempts=attempt - 1)
            client = make_mail_client(preferred_provider, disabled)
            if client is None:
                slog.err("tidak ada provider email yang tersedia")
                return AccountResult(email="", error="no_mail_provider", attempts=attempt)
            if stop_event is not None and stop_event.is_set():   # stop bisa datang selama make_mail_client
                return last or AccountResult(email="", error="aborted", attempts=attempt - 1)
            slog.info(f"attempt {attempt}/{max_attempts} → {client.email} ({client.mode})")
            res = loop.run_until_complete(create_one(client, log=rl.child(client.email.split("@")[0][:16])))
            res.attempts = attempt
            last = res
            if res.success:
                return res
            retry, pause = _decide(res.error, client)
            if not retry:
                return res
            slog.warn(f"gagal: {res.error} → retry dalam {pause}s")
            if pause:
                time.sleep(pause)
        if last is not None:
            last.error = last.error or "max_attempts_exceeded"
            return last
        return AccountResult(email="", error="max_attempts_exceeded", attempts=max_attempts)
    finally:
        loop.close()


# ─── Batch ───────────────────────────────────────────────────────────────────
def run_batch(engine, trigger: str = "manual", count: Optional[int] = None,
              workers: Optional[int] = None, provider: Optional[str] = None,
              stop_event: Optional[threading.Event] = None,
              log: Callable[[str], None] = print) -> int:
    """Jalankan satu batch; selalu membuat baris runs dan menutupnya. Return run_id."""
    import repo

    s = repo.effective_settings(engine)
    n = int(count) if count else int(s["batch_size"])
    workers = get_safe_workers(int(workers) if workers else int(s["workers"]))
    provider = (provider or s["email_provider"] or config.EMAIL_PROVIDER).lower()
    config.apply_runtime(s)
    config.EMAIL_PROVIDER = provider          # provider eksplisit (CLI/Testing) menang atas settings — ikut divalidasi
    browser_mod.set_concurrency(int(s["browser_concurrency"]))

    run_id = repo.create_run(engine, trigger, n, workers, provider, int(s.get("config_version", 1)))
    rl = RunLogger(run_id, trigger, log=log, log_dir=str(config.LOG_DIR))
    stop = stop_event or threading.Event()
    created_ok = failed = skipped = 0
    fatal: Optional[str] = None
    error_codes: dict[str, int] = {}
    status = "failed"

    try:
        with rl.stage("persiapan"):
            rl.info(f"site={config.SITE_NAME} | slot={n} | workers={workers} | provider={provider} "
                    f"| chain={provider_chain(provider)} | attempts/slot={s['max_attempts_per_slot']}")
            rl.info(f"proxy: {proxy_mod.proxy_count()} list, {proxy_mod.bad_proxy_count()} blacklist"
                    + (", Croxy rotating aktif" if config.CROXY_BASE_PROXY else "")
                    + f" | domain: {domains.domain_count()} aktif, {len(domains.get_db_banned_domains())} banned")
            if not proxy_mod.has_proxies():
                rl.warn("tanpa proxy — pakai IP server langsung")
            if not flow_implemented():
                rl.warn("flow site masih STUB (sites/%s/flow.py) — run akan berakhir NOT_IMPLEMENTED" % config.SITE_NAME)
            problems = config.validate(require_password=True)
            for p in problems:
                rl.error(p)
            if problems:
                raise RuntimeError("konfigurasi tidak lengkap: " + "; ".join(problems))
            already = repo.count_success_last_24h(engine)
            limit = int(s["max_daily_success"])
            if already >= limit:
                rl.warn(f"batas harian tercapai ({already}/{limit}) — tidak ada slot dijalankan")
                skipped = n
                n = 0
            elif already + n > limit:
                rl.warn(f"batas harian {limit}: sudah {already}, slot dipotong {n} → {limit - already}")
                skipped = n - (limit - already)
                n = limit - already

        if n > 0:
            with rl.stage(f"pembuatan {n} akun × {workers} worker"):
                def _job(i: int) -> AccountResult:
                    if stop.is_set():
                        return AccountResult(email="", error="aborted")
                    if config.CROXY_BASE_PROXY and i > 1:
                        # beri waktu Croxy rotasi IP antar akun pada worker yang start bersamaan
                        time.sleep(min(int(s["delay_between_accounts"]), 5) * ((i - 1) % workers))
                    return run_slot(i, provider, int(s["max_attempts_per_slot"]), stop, rl)

                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"run{run_id}") as ex:
                    futures = {ex.submit(_job, i): i for i in range(1, n + 1)}
                    done = 0
                    for fut in as_completed(futures):
                        idx = futures[fut]
                        done += 1
                        try:
                            res = fut.result()
                        except Exception as fe:  # noqa: BLE001
                            res = AccountResult(email="", error=f"exception: {describe_exc(fe)[:120]}")
                        if res.success:
                            created_ok += 1
                            res.status = "standby"
                            db_insert_account(engine, res.to_dict(), run_id)
                            save_result(idx, res.to_dict())
                            rl.info(f"[{done}/{n}] STANDBY OK — {res.email} | user {res.user_id or '-'} | attempt {res.attempts}")
                        elif res.error == "aborted":
                            skipped += 1
                            rl.info(f"[{done}/{n}] dibatalkan (stop)")
                        else:
                            failed += 1
                            code = (res.error or "unknown").split(":", 1)[0]
                            error_codes[code] = error_codes.get(code, 0) + 1
                            rl.warn(f"[{done}/{n}] GAGAL — {res.error or 'unknown'} (attempt {res.attempts})")
                            if res.email:
                                res.status = "failed"
                                db_insert_account(engine, res.to_dict(), run_id)
                                save_result(idx, res.to_dict())
                            if res.error in FATAL_ERRORS and fatal is None:
                                fatal = f"{res.error}: sites/{config.SITE_NAME}/flow.py belum diimplementasi"
                                stop.set()
                                rl.error(f"fatal: {fatal} — slot tersisa dibatalkan")

        if fatal or (created_ok == 0 and failed > 0):
            status = "failed"
        elif created_ok > 0 and (failed or skipped):
            status = "partial"
        else:
            status = "success"
        error_message = fatal
        if not error_message and failed:
            top = sorted(error_codes.items(), key=lambda kv: -kv[1])[:5]
            error_message = f"{failed} slot gagal: " + "; ".join(f"{c}×{k}" for k, c in top)
    except Exception as e:  # noqa: BLE001
        status = "failed"
        error_message = describe_exc(e)
        rl.error("run gagal", exc=e)
    finally:
        rl.finish(status, ok=created_ok, failed=failed, skipped=skipped)
        try:
            repo.finish_run(engine, run_id, status, created_ok, failed, skipped,
                            error_message if status != "success" or failed else None, "\n".join(rl.lines))
        except Exception as e:  # noqa: BLE001
            log(f"finish_run error: {describe_exc(e)}")
    return run_id
