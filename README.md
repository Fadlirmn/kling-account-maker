# Kling Account Maker

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python_3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy_2-D71F00?logo=sqlalchemy&logoColor=white">
  <img alt="APScheduler" src="https://img.shields.io/badge/APScheduler-3.x-4B5563">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white">
  <img alt="Camoufox" src="https://img.shields.io/badge/Camoufox_(Firefox)-FF7139?logo=firefoxbrowser&logoColor=white">
  <img alt="pytest" src="https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white">
</p>
<p>
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js_15-000000?logo=nextdotjs&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React_19-20232A?logo=react&logoColor=61DAFB">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white">
  <img alt="Tailwind CSS" src="https://img.shields.io/badge/Tailwind_CSS_3-06B6D4?logo=tailwindcss&logoColor=white">
  <img alt="Recharts" src="https://img.shields.io/badge/Recharts-22B5BF">
  <img alt="Node.js" src="https://img.shields.io/badge/Node.js_22-5FA04E?logo=nodedotjs&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white">
  <img alt="Xvfb" src="https://img.shields.io/badge/Xvfb-headful_display-6B7280">
</p>

Pembuat pool akun standby kling.ai: batch pembuatan akun lewat browser anti-detect
(Camoufox/Firefox), OTP dari provider email sementara / webhook domain sendiri, proxy rotasi,
disimpan di PostgreSQL/SQLite, dikontrol dari dashboard (jadwal harian, isi ulang otomatis sampai target pool,
riwayat run + log, kelola & ekspor akun). Tidak ada trigger manual di dashboard: batch jalan dari
scheduler atau CLI.

> **Status flow site:** `backend/sites/kling/flow.py` masih **stub** (`IS_STUB = True`). Seluruh
> infrastruktur jalan; setiap batch berakhir `NOT_IMPLEMENTED` sampai langkah signup kling.ai
> diisi (lihat kontrak di docstring file itu dan `backend/sites/kling/selectors.py`).

| Folder     | Isi                                                                 | Image                 |
|------------|---------------------------------------------------------------------|-----------------------|
| `webapp/`  | Dashboard Next.js 15 (App Router), login HMAC, proxy API            | `kling-maker/webapp`  |
| `backend/` | FastAPI + APScheduler + engine creator (Camoufox, mail, proxy, DB)  | `kling-maker/backend` |
| `deploy/`  | `init-user.sh`, `preflight.sh`, `setup-postgres.sh`                 | —                     |

### Stack

| Lapisan | Teknologi |
|---|---|
| Backend | Python 3.11 · FastAPI + Uvicorn · APScheduler · SQLAlchemy 2 Core (psycopg 3 / SQLite WAL) · openpyxl · pytest |
| Browser | Camoufox 0.4.11 (Firefox anti-detect, geoip dari proxy) · Playwright 1.60 · Xvfb `:99` di container |
| Email/OTP | Cloudflare Email Routing → Worker (webhook), Go TempMail, 1secmail, mail.tm, GPTMail |
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS 3 (token CSS var) · Recharts · Material Symbols |
| Auth | Cookie sesi HMAC-SHA256 (Web Crypto, edge middleware) · user tambahan scrypt di tabel `users` |
| Runtime | Docker Compose (`kling-backend` 8010, `kling-webapp` 3201, profile `creator`) · Node 22 alpine · python:3.11-slim |
| Konfigurasi | `backend/config.json` (non-rahasia) · `.env` (kredensial) · tabel `settings` (runtime dari dashboard) |

## Quick Start (Docker)

```bash
cp .env.example .env                          # kredensial: KLING_DEFAULT_PASSWORD, proxy, DB (setting app di backend/config.json)
bash deploy/init-user.sh admin 'password'     # user login dashboard + AUTH_SECRET → .env
bash deploy/preflight.sh                      # cek .env, GeoIP mmdb, provider, port, compose, DB
docker compose up -d --build                  # backend 127.0.0.1:8010 + webapp 127.0.0.1:3201
curl http://127.0.0.1:8010/api/health         # {"ok":true,"db":"sqlite|postgresql","flow_implemented":false,...}
```

Buka http://127.0.0.1:3201 → login. Batch pertama jalan sesuai jadwal (`Settings → Umum`) atau isi ulang
otomatis; untuk memicu sekarang pakai CLI: `docker compose run --rm creator --pre-create 3`.
Sebelum ada akun, semua blok menampilkan `Data riil <objek> akan tampil di sini setelah run pertama.`

## Arsitektur

```
┌──────────────────────────────────────────────────────────────┐
│ webapp (Next.js 15)  127.0.0.1:3201                          │
│  pages: /, /accounts, /settings, /settings/logs,             │
│         /settings/logs/[id], /settings/users                 │
│  middleware: session cookie HMAC (7 hari), proteksi /api/*   │
│  proxy: /api/backend/* → http://backend:8000/api/*           │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────┐
│ backend (FastAPI + APScheduler)  127.0.0.1:8010              │
│  api.py      REST /api/{health,summary,runs,runs/{id}/log,   │
│              runs/stop,accounts,accounts/trend,              │
│              accounts/export.xlsx|csv|json,settings,users}   │
│  scheduler   cron schedule_time (03:00 WIB) batch harian,    │
│              interval refill sampai standby_target, purge    │
│  core/runner run_batch: settings → proxy → BrowserSession →  │
│              sites/kling/flow → retry/fallback → repo        │
│  core/       mail/ (webhook, tempmail, 1secmail, mail.tm,    │
│              gptmail), proxy, domains, browser, otp, ram     │
│  config      backend/config.json (non-rahasia) + .env (rahasia)│
│  Camoufox (Firefox) headful di Xvfb :99, geoip dari proxy,   │
│  satu batch pada satu waktu (_RUNNING), stop event           │
└──────────────────────────────┬───────────────────────────────┘
                               │ DATABASE_URL (kosong → SQLite)
                     PostgreSQL di host (host.docker.internal)

Tabel: runs · kling_accounts · banned_domains · settings · users   (models.py, metadata.create_all)
```

Status akun: `pending → standby → active → exhausted → used | banned`; slot gagal tercatat `failed`
dengan kode error terakhir. Status run: `running → success | partial | failed`.

## Konfigurasi: `backend/config.json` (non-rahasia) vs `.env` (kredensial)

| File | Isi | Contoh |
|---|---|---|
| `backend/config.json` | setting aplikasi non-rahasia, **ikut repo**: `site.signup_url`, `scheduler.enabled`, `email.*` (provider, prefix, sender_filter, otp_phrases, otp_length, webhook_otp_path, custom_domains), `proxy.bad_cooldown`, `browser.*`, `defaults.*` (nilai awal tabel settings: workers, batch_size, max_daily_success, standby_target, schedule_time, …) | `"email": {"provider": "mailtm"}` |
| `backend/config.local.json` | override per mesin (gitignored), struktur sama | `{"defaults": {"workers": 1}}` |
| `.env` | **kredensial & deploy saja**: `DATABASE_URL`, `DASHBOARD_USER/PASSWORD`, `AUTH_SECRET`, `KLING_DEFAULT_PASSWORD`, `CLOUDFLARE_WORKER_URL`, `TEMPMAIL_API_URL/SECRET`, `PROXY_LIST`, `CROXY_BASE_PROXY`, port (`DASHBOARD_PORT`, `API_PORT`), `NEXT_PUBLIC_APP_NAME` | lihat `.env.example` |
| tabel `settings` (DB) | nilai runtime yang diubah dari dashboard Settings; menimpa `defaults.*` | — |

Prioritas backend: **env var > config.local.json > config.json > default kode**. Env var dengan nama lama
(`EMAIL_PROVIDER`, `WORKERS`, `ENABLE_SCHEDULER`, …) tetap bisa menimpa config.json — berguna untuk Docker/CI.
Di compose `config.json` di-mount read-only; edit lalu `docker compose restart backend`.

## Data dummy

`cd backend && .venv/bin/python seed_dummy.py --reset` mengisi 14 hari run + ~150 akun `*@dummy.kling.test`
(status campur, log bergaya RunLogger) supaya dashboard punya isi sebelum flow jadi. `--reset` hanya menghapus
data dummy itu.

## Creator

- **Pemicu**: scheduler (batch harian `schedule_time`, isi ulang ke `standby_target`) atau CLI. Tidak ada
  tombol Run Now / `POST /api/runs`. Stop batch yang sedang jalan: `POST /api/runs/stop` (tombol Stop di topbar
  muncul saat running; slot baru dibatalkan, attempt berjalan diselesaikan).
- **CLI tanpa backend**: `docker compose run --rm creator --pre-create 3` atau lokal
  `cd backend && .venv/bin/python account_creator.py --pre-create 3 --workers 2`.
- Tiap slot: pilih provider email (fallback berantai), proxy berikutnya, launch Camoufox
  (`geoip=True`, `humanize`, routing hemat bandwidth), jalankan flow site, lalu klasifikasi error:
  `DOMAIN_BLOCKED:*` → domain di-ban, `PROXY_FLAGGED*` → proxy blacklist + jeda, `otp timeout` →
  retry provider, `NOT_IMPLEMENTED` → run dihentikan.
- Log per run: `backend/logs/run_<id>.log` (live) + kolom `runs.log`; format
  `[HH:MM:SS] [+12.3s] LEVEL  pesan`, tahap `── persiapan ──`, `── pembuatan N akun × W worker ──`.

### Jadwal (APScheduler di container backend, `ENABLE_SCHEDULER=true`)

| Job | Kapan |
|---|---|
| Batch harian | cron `schedule_time` WIB (03:00) + jitter `schedule_jitter_minutes`; `batch_size` slot |
| Isi ulang otomatis | tiap `refill_interval_minutes` (60): kalau `standby < standby_target` → batch `min(kurang, batch_size)`. Dilewati kalau batas harian tercapai, batch lain jalan, atau run terakhir `NOT_IMPLEMENTED` |
| Hapus run lama | 03:30 WIB kalau `retention_days > 0` (akun tetap, `run_id` → NULL) |

## Export

Halaman **Accounts** → tombol Excel / CSV / JSON (ikut filter status):
`GET /api/accounts/export.xlsx|csv|json?status=`; preview `GET /api/export/preview?rows=5`.
Cookies per akun: `GET /api/accounts/{id}/cookies` (tombol di dialog detail akun).

## Production (server)

```bash
sudo bash deploy/setup-postgres.sh            # role + DB + listen_addresses + pg_hba subnet Docker
git clone <repo> KlingAi-Account-Maker && cd KlingAi-Account-Maker
cp .env.example .env                          # DATABASE_URL, KLING_DEFAULT_PASSWORD, proxy (kredensial saja)
bash deploy/init-user.sh <user> '<password>'
python3 backend/scripts/download_geoip.py     # kalau backend/GeoLite2-City.mmdb belum ada
bash deploy/preflight.sh
docker compose up -d --build
docker compose logs -f backend                # boot pertama: download Camoufox ~1.3GB ke backend/camoufox_cache
```

> **Hemat waktu boot pertama:** kalau mesin ini sudah punya browser Camoufox (`python -m camoufox fetch` lokal),
> salin cache-nya sebelum `up` supaya container tidak mengunduh ulang 1.3GB:
> `mkdir -p backend/camoufox_cache/camoufox && cp -a ~/.cache/camoufox/. backend/camoufox_cache/camoufox/`.
> Webapp baru naik setelah healthcheck backend lolos (start_period 180 s); selama unduhan berjalan `docker compose up`
> menampilkan "waiting" di backend — itu normal.

## Development tanpa Docker

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/patch_playwright.sh .venv && .venv/bin/python -m camoufox fetch
.venv/bin/python -m pytest tests/ -q                       # repo, runlog, runner, api
.venv/bin/uvicorn api:app --port 8000 --reload
.venv/bin/python account_creator.py --pre-create 1

cd webapp && npm install && API_BASE_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

## Mengisi flow kling.ai

1. Riset halaman signup (email+password? OTP kode atau link? captcha/Cloudflare?).
2. Isi `backend/sites/kling/selectors.py`; set `site.signup_url`, `email.otp_phrases`, `email.sender_filter` di `backend/config.json`.
3. Implementasi `create_account()` di `backend/sites/kling/flow.py` sesuai kontrak docstring; hapus `IS_STUB`.
4. Uji: `DEBUG_SCREENSHOTS=true .venv/bin/python test_single.py`, lalu `account_creator.py --pre-create 1`.

## Troubleshooting

- **Run `failed: NOT_IMPLEMENTED`** → flow site belum diisi (lihat bagian di atas); alert kuning di Dashboard.
- **Run `failed: konfigurasi tidak lengkap`** → `KLING_DEFAULT_PASSWORD` kosong di `.env` atau provider butuh kredensial (lihat log run).
- **`NS_ERROR_NET_INTERRUPT` / browser gagal launch** → `backend/GeoLite2-City.mmdb` hilang (mount jadi directory) atau proxy mati; `preflight.sh` mengecek.
- **Firefox crash / heap corruption** → turunkan `browser_concurrency` di Settings; `shm_size` 1gb sudah di compose.
- **Semua proxy blacklist** → cooldown `PROXY_BAD_COOLDOWN` (300 s); run tetap lanjut tanpa proxy dengan WARN.
- **PostgreSQL tidak konek dari container** → `DATABASE_URL` harus `host.docker.internal`; cek `pg_hba` subnet Docker (`setup-postgres.sh`).

## Catatan

- Keputusan desain: `DECISION_LOG.md`. Riwayat diskusi: `discussions/YYYY-MM-DD_slug/`.
- Sumber infrastruktur: `canva-leo-akun-create` (engine generik), `Scraping-Shopee-Seller` (gaya kode + dashboard).
