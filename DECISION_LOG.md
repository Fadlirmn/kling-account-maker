# Decision Log — KlingAi Account Maker

## 1. Port dari canva-leo-akun-create, hanya engine generik
- **Decision:** Ambil infrastruktur (DB, proxy, domain, email/OTP, browser anti-detect, runner, Docker) dari
  `canva-leo-akun-create`; buang bot Telegram, menu CLI, admin manager (team/Leonardo OAuth), credit rotator,
  integrasi platform/head-agent, dan semua URL/selector Canva.
- **Rationale:** Target site berbeda (kling.ai); bagian UI dan site-specific tidak bisa dipakai ulang.
  Sumber `canva_bulk_creator.py` dipilih sebagai basis karena salinan paling baru (fix OTP generic, RAM guard, MMDB check).

## 2. Layout modular `core/` + `sites/<site>/`
- **Decision:** Pecah file monolit 4000+ baris menjadi modul tunggal per fungsi. Flow site diisolasi di
  `sites/kling/flow.py` dan dimuat runner lewat `importlib` berdasarkan `config.SITE_NAME`.
- **Rationale:** Di sumber, launch browser, parser proxy, log, dan routing disalin 3-5 kali di file berbeda
  (dan saling sedikit berbeda). Satu tempat per fungsi memudahkan perbaikan dan penggantian site.

## 3. Flow Kling stub-first dengan kontrak exception
- **Decision:** `flow.create_account()` raise `NotImplementedError` sampai riset halaman selesai. Runner memetakan
  `NotImplementedError → NOT_IMPLEMENTED` (non-retryable, batch dihentikan). Flow berkomunikasi dengan runner lewat
  `DomainBlocked`, `ProxyFlagged`, `OtpTimeout`, `FormNotFound`; flow tidak menyentuh blacklist proxy/domain.
- **Rationale:** Infrastruktur bisa diverifikasi end-to-end tanpa menunggu riset site. Di sumber, kode error
  berupa string bebas (`DOMAIN_BLOCKED:` tidak pernah diproduksi) sehingga cabang retry mati.

## 4. Fix translator SQL SQLite
- **Decision:** `_pg_to_sqlite_sql` mengubah `INSERT INTO t ... ON CONFLICT ... DO UPDATE SET ...` menjadi
  `INSERT OR REPLACE INTO t ...` secara generik (regex nama tabel), bukan hardcode nama tabel.
- **Rationale:** Versi sumber menghasilkan SQL invalid yang menyebut `canva_accounts_berpassword` untuk tabel apa pun.

## 5. `banned_domains` dibuat di `init_db()`
- **Decision:** DDL `banned_domains` dipindah dari CREATE TABLE lazy di bulk creator ke `db.init_db()`;
  `domains.ban_domain_in_db()` ditambahkan dan dipanggil runner saat `DOMAIN_BLOCKED`.
- **Rationale:** Di sumber, `account_creator.py` membaca tabel yang tidak pernah dibuatnya; schema harus satu sumber.

## 6. Tidak ada path/password hardcode
- **Decision:** `KLING_DEFAULT_PASSWORD` wajib (CLI gagal jika kosong). Path TempMail hanya dari env dengan
  default relatif `data/`. `TEMPMAIL_SECRET` tanpa default ajaib. Prefix email, filter pengirim, frasa OTP,
  endpoint webhook semua env (`EMAIL_PREFIX`, `MAIL_SENDER_FILTER`, `OTP_PHRASES`, `WEBHOOK_OTP_PATH`).
- **Rationale:** Sumber punya password default hardcode dan path `/home/sumbul/...` yang gagal di VPS/Docker.

## 7. `blacklist_proxy` dipakai; manual OTP opsional; tweak sistem dijaga
- **Decision:** Runner memanggil `blacklist_proxy()` pada `ProxyFlagged` dan error terklasifikasi proxy
  (di sumber `account_creator.py` fungsi ini tidak pernah dipanggil). Input OTP manual via stdin hanya jika
  `MANUAL_OTP=true` (default false; memblok thread di Docker). `sysctl`/remount `/dev/shm` hanya jika root di Docker.
  Tmp dir per-browser yang tidak pernah dipakai dibuang. Pref popup-blocker (khusus OAuth popup Leonardo) jadi opsi `allow_popups`.

## 8. Docker mengikuti layout stabil sumber
- **Decision:** Service/container `kling-creator` (nama unik), `restart: unless-stopped`, Xvfb `:99`, GeoIP
  di-build ke image dan di-mount read-only, pin `camoufox[geoip]==0.4.11` + `playwright==1.60.0`.
- **Rationale:** Decision #3, #10, #11 sumber: Firefox butuh DISPLAY untuk WebGL; mmdb hilang → Docker membuat
  directory → `NS_ERROR_NET_INTERRUPT`; nama container bentrok di VPS; patch bergantung layout bundle Playwright.

## 9. Layout repo `backend/` + `webapp/` dan DB layer SQLAlchemy Core (gaya Scraping-Shopee-Seller)
- **Decision:** Engine dipindah ke `backend/`; `core/db.py` (psycopg2 + translator SQL manual) diganti `db.py`
  (`get_engine` lru_cache, `postgresql+psycopg://`, SQLite WAL), `models.py` (Core `Table` + `_ensure_columns`),
  `repo.py` (semua fungsi terima `engine`). Tabel baru `runs`, `settings`, `users`; `kling_accounts` + `run_id`, `error`.
- **Rationale:** Konsisten dengan project Shopee (satu gaya kode di semua project), settings bisa diubah dari
  dashboard tanpa restart, migrasi kolom aman untuk SQLite persisten di deployment.

## 10. RunLogger per run, thread-safe
- **Decision:** `runlog.py` disalin dari Shopee + `threading.Lock` di `_raw` dan `child(prefix)` (adapter interface
  `ok/err/info/warn/step` yang dipakai flow site). Runner menulis log slot lewat `rl.child(...)`.
- **Rationale:** Worker ThreadPool (satu per akun) emit bersamaan; tanpa lock baris tercampur di file dan `.lines`.

## 11. Settings runtime di tabel DB; env hanya default awal
- **Decision:** `DEFAULT_SETTINGS` dibangun dari `core.config` (env); `repo.get_settings` menimpa dengan baris tabel.
  `run_batch` memanggil `config.apply_runtime()` + `browser.set_concurrency()` sebelum batch. `PROXY_LIST`,
  domain, kredensial provider, `KLING_DEFAULT_PASSWORD` tetap env-only.
- **Rationale:** Pola Shopee (`settings` key/value JSON + `config_version`); hal yang menyentuh rahasia atau
  dibaca saat import (daftar proxy) tidak cocok diubah dari UI.

## 12. Dashboard = salinan webapp Shopee dengan halaman Kling
- **Decision:** `webapp/` disalin utuh (globals.css, ui/form/Alert/Dialog/LogView/Shell/Sidebar/Topbar, auth HMAC,
  proxy `/api/backend/*`, users). Halaman Shopee dihapus; halaman baru: Dashboard, Accounts, Settings (Umum),
  Settings ▸ Logs (+detail), Settings ▸ User. Runs tetap di `/settings/logs` persis Shopee (`/runs` redirect).
- **Rationale:** Permintaan user "style Scraping-Shopee-Seller"; komponen sudah teruji di produksi.

## 13. Stop event + fatal `NOT_IMPLEMENTED`
- **Decision:** `POST /api/runs/stop` men-set `threading.Event` yang dicek `run_slot` sebelum attempt berikut dan
  `_job` sebelum slot mulai; browser yang sedang jalan diselesaikan (tanpa kill). Slot `NOT_IMPLEMENTED` men-set
  event yang sama dan run berstatus `failed` dengan `error_message` berawalan `NOT_IMPLEMENTED`; `job_refill`
  melewati run berikutnya selama run terakhir masih begitu.
- **Rationale:** Hentikan batch tanpa merusak state browser/DB; cegah run gagal otomatis tiap jam saat flow stub.

## 14. Konfigurasi non-rahasia di `backend/config.json`, kredensial di `.env`
- **Decision:** Semua knob aplikasi (provider email, prefix, OTP, browser, default worker/batch/jadwal, master switch
  scheduler) pindah ke `backend/config.json` (ikut repo) dengan override `config.local.json` (gitignored). `.env` hanya
  kredensial + variabel deploy (port, nama app). Prioritas `env > config.local.json > config.json > default kode`
  (`core/config.py`); env var lama tetap diterima untuk Docker/CI. Compose me-mount `config.json` read-only.
- **Rationale:** Permintaan user; `.env` jadi pendek dan jelas rahasia saja, setting aplikasi ter-version-control dan
  bisa di-diff. Preferensi ini disimpan sebagai default untuk project berikutnya.
