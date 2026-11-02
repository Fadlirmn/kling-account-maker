"""
core.bootstrap — side-effect module, HARUS di-import paling awal.

Dilakukan sekali saat import:
  1. Set env Firefox/Camoufox agar jalan di VPS/Docker tanpa sandbox & GPU.
  2. Hot-patch bug Playwright Firefox coreBundle.js (pageError.location null).
  3. load_dotenv: ENV_FILE env, atau .env di root repo (../.env), fallback backend/.env; override=True.
  4. Validasi & heal GeoIP MMDB (hapus jika corrupt agar Camoufox download ulang).

Dipusatkan di sini supaya tidak
diulang di setiap launch browser.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent          # backend/
REPO_ROOT = PROJECT_ROOT.parent                                  # root repo (.env, docker-compose.yml)

# ─── 1. Firefox sandbox / GPU env ────────────────────────────────────────────
# Firefox sandbox butuh kernel user namespaces; di banyak VPS diblokir →
# disable semua sandbox. Software rendering agar WebGL tetap ada (fingerprint realistis).
_FIREFOX_ENV = {
    "MOZ_DISABLE_CONTENT_SANDBOX": "1",
    "MOZ_DISABLE_GPU_SANDBOX": "1",
    "MOZ_DISABLE_RDD_SANDBOX": "1",
    "MOZ_DISABLE_SOCKET_PROCESS_SANDBOX": "1",
    "MOZ_DISABLE_PROCESS_SANDBOX": "1",
    "MOZ_SANDBOX_DISABLE": "1",
    "LIBGL_ALWAYS_SOFTWARE": "1",
    "MOZ_DISABLE_GFX_SANITY_TEST": "1",
    "MOZ_DISABLE_PANGO_SANITY_TEST": "1",
    "MOZ_WEBGL_FORCE_ENABLED": "1",
    "MESA_GL_VERSION_OVERRIDE": "4.5",
}
for _k, _v in _FIREFOX_ENV.items():
    os.environ.setdefault(_k, _v)


# ─── 2. Hot-patch Playwright Firefox bug ─────────────────────────────────────
def patch_playwright_firefox_bug() -> None:
    """Fix ValidationError: location.url expected string, got undefined."""
    try:
        import playwright
        core_bundle = Path(playwright.__file__).parent / "driver" / "package" / "lib" / "coreBundle.js"
        if not core_bundle.exists():
            return
        content = core_bundle.read_text(encoding="utf-8")
        needles = ("pageError.location.url", "pageError.location.lineNumber", "pageError.location.columnNumber")
        if not any(n in content for n in needles):
            return
        print("⚠️  [patch] Playwright Firefox coreBundle.js bug terdeteksi. Memperbaiki...", flush=True)
        content = (content
                   .replace("pageError.location.url", "pageError.location ? pageError.location.url : ''")
                   .replace("pageError.location.lineNumber", "pageError.location ? pageError.location.lineNumber : 0")
                   .replace("pageError.location.columnNumber", "pageError.location ? pageError.location.columnNumber : 0"))
        core_bundle.write_text(content, encoding="utf-8")
        print("✅ [patch] Playwright Firefox coreBundle.js berhasil diperbaiki!", flush=True)
    except Exception as e:  # pragma: no cover
        print(f"⚠️  [patch] Gagal hot-patch Playwright: {e}", flush=True)


patch_playwright_firefox_bug()


# ─── 3. Load .env ────────────────────────────────────────────────────────────
# override=True: .env selalu menang atas env shell (fix PROXY_LIST kosong di Docker).
def _env_file() -> Path:
    explicit = os.getenv("ENV_FILE", "").strip()
    if explicit:
        return Path(explicit)
    root_env = REPO_ROOT / ".env"
    return root_env if root_env.exists() else PROJECT_ROOT / ".env"


ENV_FILE = _env_file()
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_FILE, override=True)
except ImportError:  # pragma: no cover
    pass


# ─── 4. Validasi & heal GeoIP MMDB ───────────────────────────────────────────
def check_and_heal_mmdb() -> bool:
    """Return True jika MMDB valid. Jika corrupt → hapus agar Camoufox download ulang."""
    mmdb_path = None
    try:
        from camoufox.locale import MMDB_FILE
        import geoip2.database
        mmdb_path = Path(str(MMDB_FILE))
        with geoip2.database.Reader(str(mmdb_path)):
            return True
    except Exception as e:
        print(f"[GeoIP] MMDB tidak valid atau tidak ditemukan: {e}", flush=True)
        if mmdb_path and mmdb_path.exists():
            try:
                mmdb_path.unlink()
                print(f"[GeoIP] File corrupt dihapus: {mmdb_path} — Camoufox akan download ulang otomatis.", flush=True)
            except Exception as ue:
                print(f"[GeoIP] Gagal menghapus file corrupt {mmdb_path}: {ue}", flush=True)
        return False


check_and_heal_mmdb()
