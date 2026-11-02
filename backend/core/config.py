"""
core.config — konfigurasi aplikasi jadi konstanta modul.

Sumber, urutan prioritas (yang di atas menang):
  1. env var (hanya untuk override Docker/CI & KREDENSIAL — .env)
  2. backend/config.local.json  (opsional, gitignored, override lokal)
  3. backend/config.json        (non-rahasia, ikut repo)
  4. default di kode

Kredensial TIDAK pernah ada di config.json: DATABASE_URL, KLING_DEFAULT_PASSWORD, CLOUDFLARE_WORKER_URL,
KURMAMAIL_URL/API_KEY, TEMPMAIL_API_URL/SECRET, PROXY_LIST, CROXY_BASE_PROXY → .env saja.
Path runtime (DATA_DIR, LOG_DIR, ...) juga env karena Docker mengarahkannya ke /data/*.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.bootstrap import PROJECT_ROOT  # memastikan .env sudah di-load

CONFIG_FILE = Path(os.getenv("CONFIG_FILE", "") or PROJECT_ROOT / "config.json")
CONFIG_LOCAL_FILE = CONFIG_FILE.with_name("config.local.json")


def _load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f"⚠️  [config] {path.name} tidak bisa dibaca ({e}) — diabaikan", flush=True)
        return {}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


CONFIG: dict = _deep_merge(_load_json(CONFIG_FILE), _load_json(CONFIG_LOCAL_FILE))
CONFIG_SOURCES = [p.name for p in (CONFIG_FILE, CONFIG_LOCAL_FILE) if p.exists()]


def _cfg(path: str, default: Any = None) -> Any:
    """Ambil nilai bertitik dari CONFIG, mis. _cfg('email.provider')."""
    cur: Any = CONFIG
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _as_bool(v: Any, default: bool) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _as_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return []


def _val(env_key: str, cfg_path: str, default: Any) -> Any:
    """env (jika diset & tidak kosong) > config.json > default."""
    e = _env(env_key)
    if e != "":
        return e
    v = _cfg(cfg_path)
    return default if v is None else v


def _str(env_key: str, cfg_path: str, default: str = "") -> str:
    return str(_val(env_key, cfg_path, default)).strip()


def _int(env_key: str, cfg_path: str, default: int) -> int:
    return _as_int(_val(env_key, cfg_path, default), default)


def _bool(env_key: str, cfg_path: str, default: bool) -> bool:
    return _as_bool(_val(env_key, cfg_path, default), default)


def _list(env_key: str, cfg_path: str, default: list[str] | None = None) -> list[str]:
    return _as_list(_val(env_key, cfg_path, default or []))


# ─── Paths (env; di Docker diarahkan ke /data/*) ─────────────────────────────
def _path(key: str, default: Path) -> Path:
    return Path(_env(key) or default)


DATA_DIR     = _path("DATA_DIR", PROJECT_ROOT / "data")
COOKIES_DIR  = _path("COOKIES_DIR", PROJECT_ROOT / "cookies")
RESULT_DIR   = _path("RESULT_DIR", PROJECT_ROOT / "result")      # debug screenshots
LOG_DIR      = _path("LOG_DIR", PROJECT_ROOT / "logs")           # run_<id>.log
EXPORT_DIR   = _path("EXPORT_DIR", PROJECT_ROOT / "exports")
RESULTS_FILE = DATA_DIR / _str("RESULTS_FILE", "defaults.results_file", "results_kling.txt")
DOMAIN_FILE  = PROJECT_ROOT / "domain.txt"
for _d in (DATA_DIR, COOKIES_DIR, RESULT_DIR, LOG_DIR, EXPORT_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

# ─── Target site ─────────────────────────────────────────────────────────────
SITE_NAME              = _str("SITE_NAME", "site.name", "kling")
KLING_SIGNUP_URL       = _str("KLING_SIGNUP_URL", "site.signup_url", "")   # TODO: isi setelah riset kling.ai
KLING_DEFAULT_PASSWORD = _env("KLING_DEFAULT_PASSWORD")                     # KREDENSIAL — .env saja

# ─── Scheduler (master switch) ───────────────────────────────────────────────
ENABLE_SCHEDULER = _bool("ENABLE_SCHEDULER", "scheduler.enabled", True)

# ─── Email / OTP ─────────────────────────────────────────────────────────────
EMAIL_PROVIDER         = _str("EMAIL_PROVIDER", "email.provider", "1secmail").lower()
ALLOW_GPTMAIL_FALLBACK = _bool("ALLOW_GPTMAIL_FALLBACK", "email.allow_gptmail_fallback", True)
EMAIL_PREFIX           = _str("EMAIL_PREFIX", "email.prefix", "kling_")
MAIL_SENDER_FILTER     = [s.lower() for s in _list("MAIL_SENDER_FILTER", "email.sender_filter", ["kling", "klingai"])]
OTP_PHRASES            = _list("OTP_PHRASES", "email.otp_phrases")
OTP_LENGTH             = _int("OTP_LENGTH", "email.otp_length", 6)
OTP_TIMEOUT            = _int("OTP_TIMEOUT", "email.otp_timeout", 180)
MANUAL_OTP             = _bool("MANUAL_OTP", "email.manual_otp", False)
WEBHOOK_OTP_PATH       = _str("WEBHOOK_OTP_PATH", "email.webhook_otp_path", "/get-otp")
CLOUDFLARE_WORKER_URL  = _env("CLOUDFLARE_WORKER_URL").rstrip("/")          # KREDENSIAL (URL privat) — .env

# Kurma Mail (email-custom): inbox catch-all + GET /api/emails/lookup dengan X-API-Key
KURMAMAIL_URL     = _env("KURMAMAIL_URL").rstrip("/")                      # .env
KURMAMAIL_API_KEY = _env("KURMAMAIL_API_KEY")                              # KREDENSIAL — .env

# Local TempMail (Go service)
TEMPMAIL_API_URL     = _env("TEMPMAIL_API_URL").rstrip("/")                 # .env
TEMPMAIL_SECRET      = _env("TEMPMAIL_SECRET")                              # KREDENSIAL — .env
TEMPMAIL_DOMAIN_FILE = _str("TEMPMAIL_DOMAIN_FILE", "email.tempmail_domain_file", "") or str(DATA_DIR / "tempmail_domains.txt")
TEMPMAIL_DB_PATH     = _str("TEMPMAIL_DB_PATH", "email.tempmail_db_path", "") or str(DATA_DIR / "tempmail.db")

# Custom domains: domain.txt (prioritas) → env CUSTOM_DOMAINS → config email.custom_domains
CUSTOM_DOMAINS: list[str] = []
if DOMAIN_FILE.exists():
    CUSTOM_DOMAINS = [
        ln.strip() for ln in DOMAIN_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
if not CUSTOM_DOMAINS:
    CUSTOM_DOMAINS = _list("CUSTOM_DOMAINS", "email.custom_domains")

# ─── Proxy ───────────────────────────────────────────────────────────────────
PROXY_LIST         = _as_list(_env("PROXY_LIST"))                           # KREDENSIAL — .env
CROXY_BASE_PROXY   = _env("CROXY_BASE_PROXY")                               # KREDENSIAL — .env
PROXY_FILES        = [DATA_DIR / "proxy.txt", PROJECT_ROOT / "proxy.txt"]
PROXY_BAD_COOLDOWN = _int("PROXY_BAD_COOLDOWN", "proxy.bad_cooldown", 300)  # detik

# ─── Browser ─────────────────────────────────────────────────────────────────
BROWSER_LOCALE    = _str("BROWSER_LOCALE", "browser.locale", "en-US")
ROUTING_ALLOWLIST = [s.lower() for s in _list("ROUTING_ALLOWLIST", "browser.routing_allowlist")]
RAM_PER_WORKER_MB = _int("RAM_PER_WORKER_MB", "browser.ram_per_worker_mb", 700)

# ─── Default awal tabel settings (dashboard menimpa saat runtime) ────────────
WORKERS                = _int("WORKERS", "defaults.workers", 2)
BROWSER_CONCURRENCY    = _int("BROWSER_CONCURRENCY", "defaults.browser_concurrency", 2)
BATCH_SIZE             = _int("BATCH_SIZE", "defaults.batch_size", 10)
MAX_DAILY_SUCCESS      = _int("MAX_DAILY_SUCCESS", "defaults.max_daily_success", 500)
STANDBY_TARGET         = _int("STANDBY_TARGET", "defaults.standby_target", 20)
REFILL_INTERVAL_MIN    = _int("REFILL_INTERVAL_MINUTES", "defaults.refill_interval_minutes", 60)
SCHEDULE_ENABLED       = _bool("SCHEDULE_ENABLED", "defaults.enable_scheduler", True)
SCHEDULE_TIME          = _str("SCHEDULE_TIME", "defaults.schedule_time", "03:00")
SCHEDULE_JITTER_MIN    = _int("SCHEDULE_JITTER_MINUTES", "defaults.schedule_jitter_minutes", 20)
MAX_ATTEMPTS_PER_SLOT  = _int("MAX_ATTEMPTS_PER_SLOT", "defaults.max_attempts_per_slot", 8)
DELAY_BETWEEN_ACCOUNTS = _int("DELAY_BETWEEN_ACCOUNTS", "defaults.delay_between_accounts", 30)
DEBUG_SCREENSHOTS      = _bool("DEBUG_SCREENSHOTS", "defaults.debug_screenshots", False)
RETENTION_DAYS         = _int("RETENTION_DAYS", "defaults.retention_days", 0)

# ─── Database (dipakai db.py) ────────────────────────────────────────────────
DATABASE_URL = _env("DATABASE_URL")                                          # KREDENSIAL — .env
SQLITE_PATH  = _path("SQLITE_PATH", DATA_DIR / "kling_accounts.db")

# ─── Override runtime dari tabel settings (dashboard) ───────────────────────
_RUNTIME_KEYS = {
    "email_provider": "EMAIL_PROVIDER",
    "max_daily_success": "MAX_DAILY_SUCCESS",
    "delay_between_accounts": "DELAY_BETWEEN_ACCOUNTS",
    "max_attempts_per_slot": "MAX_ATTEMPTS_PER_SLOT",
    "browser_concurrency": "BROWSER_CONCURRENCY",
    "debug_screenshots": "DEBUG_SCREENSHOTS",
    "workers": "WORKERS",
}


def apply_runtime(settings: dict) -> None:
    """Terapkan nilai tabel settings ke konstanta modul (dipanggil runner sebelum batch)."""
    g = globals()
    for key, const in _RUNTIME_KEYS.items():
        if key in settings and settings[key] is not None:
            g[const] = settings[key]


def password_problems(pw: str) -> list[str]:
    """Satu password untuk semua akun: min 8 karakter, ada huruf kecil, huruf besar, angka, dan simbol."""
    if not pw:
        return ["KLING_DEFAULT_PASSWORD belum diset di .env"]
    out = []
    if len(pw) < 8:
        out.append("KLING_DEFAULT_PASSWORD minimal 8 karakter")
    if not any(c.islower() for c in pw): out.append("KLING_DEFAULT_PASSWORD harus ada huruf kecil")
    if not any(c.isupper() for c in pw): out.append("KLING_DEFAULT_PASSWORD harus ada huruf besar")
    if not any(c.isdigit() for c in pw): out.append("KLING_DEFAULT_PASSWORD harus ada angka")
    if not any(not c.isalnum() for c in pw): out.append("KLING_DEFAULT_PASSWORD harus ada simbol (mis. # ! @)")
    return out


def validate(require_password: bool = True) -> list[str]:
    """Return daftar masalah konfigurasi (kosong = OK). Dipanggil CLI/runner sebelum run."""
    problems = []
    if require_password:
        problems += password_problems(KLING_DEFAULT_PASSWORD)
    if EMAIL_PROVIDER not in ("kurmamail", "webhook", "local_tempmail", "1secmail", "mailtm", "gptmail"):
        problems.append(f"email.provider tidak dikenal: {EMAIL_PROVIDER}")
    if EMAIL_PROVIDER == "kurmamail":
        if not (KURMAMAIL_URL and KURMAMAIL_API_KEY):
            problems.append("provider kurmamail butuh KURMAMAIL_URL dan KURMAMAIL_API_KEY (.env)")
        if not CUSTOM_DOMAINS:
            problems.append("provider kurmamail butuh domain.txt / email.custom_domains (domain yang di-route ke Kurma Mail)")
    if EMAIL_PROVIDER == "webhook" and not (CLOUDFLARE_WORKER_URL and CUSTOM_DOMAINS):
        problems.append("provider webhook butuh CLOUDFLARE_WORKER_URL (.env) dan domain.txt / email.custom_domains")
    if EMAIL_PROVIDER == "local_tempmail":
        if not TEMPMAIL_API_URL:
            problems.append("provider local_tempmail butuh TEMPMAIL_API_URL (.env)")
        if not TEMPMAIL_SECRET:
            problems.append("TEMPMAIL_SECRET kosong (.env)")
    return problems
