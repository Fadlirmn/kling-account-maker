# Dashboard & Gaya Kode ala Scraping-Shopee-Seller

**Tanggal:** 2026-11-02  
**Status:** selesai  
**Versi:** v3

## Konteks
Engine generik hasil port dari `canva-leo-akun-create` (core/, sites/kling stub) diminta mengikuti style
`Scraping-Shopee-Seller`: dashboard web identik look-and-feel dan pola kode backend (FastAPI + APScheduler +
SQLAlchemy Core, RunLogger, settings di DB, deploy scripts, README diagram kotak).

## Keputusan & Hasil
- **Layout** `backend/` + `webapp/` + `deploy/`; `core/db.py` psycopg2 → `db.py/models.py/repo.py` SQLAlchemy Core (psycopg 3). Tabel `runs`, `settings`, `users`, `kling_accounts(+run_id,error)`, `banned_domains`.
- **Runner** `run_batch(engine, trigger, count, workers, provider, stop_event, log) -> run_id` dengan `RunLogger` thread-safe (`child(prefix)` untuk flow), status run `success|partial|failed`, fatal `NOT_IMPLEMENTED` menghentikan slot sisa.
- **API** `api.py`: health/summary/runs/log/stop, accounts (list/detail/cookies/status/export xlsx-csv-json/trend), settings tervalidasi, users+auth; scheduler batch harian + isi ulang ke `standby_target` + purge.
- **Webapp** salinan Shopee: Dashboard (alert flow stub, metrics, tren 14 hari, run terbaru, komposisi status), Accounts (filter pill, cari, dialog detail + ubah status + download cookies), Settings Umum/Logs/User; Run Now dialog (jumlah/worker/provider), tombol Stop.
- **Verifikasi**: `pytest` 29 passed; `tsc --noEmit` bersih; `next build`; `docker compose config`.

## Tindak Lanjut
- Isi `sites/kling/flow.py` + `selectors.py` setelah riset halaman signup kling.ai; hapus `IS_STUB`.
- `docker compose up -d --build` di server (build image ditunda: koneksi lambat saat sesi ini).

---
*Dibuat otomatis oleh agent · maks. 200 kata*
