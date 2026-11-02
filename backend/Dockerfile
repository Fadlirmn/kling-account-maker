# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Kling Account Maker backend (FastAPI + APScheduler + creator)
# Base: Python 3.11-slim + Firefox/Camoufox system deps + Xvfb
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Jakarta \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    XDG_CACHE_HOME=/app/camoufox_cache \
    SQLITE_PATH=/data/db/kling_accounts.db \
    DATA_DIR=/data/db \
    COOKIES_DIR=/data/cookies \
    RESULT_DIR=/data/result \
    LOG_DIR=/data/logs \
    EXPORT_DIR=/data/exports

# ── System deps untuk Camoufox (Firefox) + Xvfb ──────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-0 libdbus-glib-1-2 \
    libx11-6 libx11-xcb1 libxcb1 libxcb-shm0 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libxrender1 libxss1 libxtst6 libxt6 \
    libnss3 libnspr4 \
    libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libpango-1.0-0 libcairo2 libcairo-gobject2 libgdk-pixbuf-2.0-0 libglib2.0-0 \
    libdrm2 libgbm1 libgl1 \
    libcups2 \
    xvfb \
    wget curl ca-certificates tzdata \
    fonts-liberation fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ──────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 -r requirements.txt

# ── Source ───────────────────────────────────────────────────────────────────
COPY . .

# ── Patch Playwright Firefox driver bug ──────────────────────────────────────
RUN bash scripts/patch_playwright.sh /usr/local || true

# ── GeoIP: salin mmdb lokal (cepat), lalu validasi/download saat build
#    (build ke image: kalau mount host hilang, jangan sampai Camoufox tanpa MMDB)
COPY requirements.txt GeoLite2-City.mmdb* /usr/local/lib/python3.11/site-packages/camoufox/
RUN python3 scripts/download_geoip.py || true

RUN chmod +x entrypoint.sh && mkdir -p /data/db /data/cookies /data/result /data/logs /data/exports /app/camoufox_cache

EXPOSE 8000

# Entrypoint: camoufox fetch (jika belum), Xvfb :99, patch, cek GeoIP, lalu exec CMD.
# Creator on-demand: docker compose run --rm creator --pre-create 3
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
