# Kling Account Maker Console (Web Dashboard)

Dashboard Next.js untuk pool akun standby Kling (ringkasan pool, daftar akun + cookies, riwayat run/batch
dengan log per slot, pengaturan creator). Backend FastAPI ada di `../backend`; web ini hanya membaca/menyuruh
lewat API-nya. Tampilan mengikuti design system **Kurma web** (Material 3 tonal: coral / violet / indigo)
yang sama dengan project Kurma lain.

## 1. Stack

| Lapisan | Pilihan |
|---|---|
| Framework | **Next.js 15 (App Router)** + **React 19** + **TypeScript strict**, `output: "standalone"` |
| UI | **Tailwind CSS 3**; semua warna → CSS variable di `src/app/globals.css` (`:root` terang, `[data-theme="dark"]` gelap). Kelas design-system (`.card .btn .pill .input .table-wrap .alert .dialog .metric .sidebar`) diletakkan di antara `@tailwind components` dan `@tailwind utilities` supaya utility tetap menang. Tanpa MUI/shadcn |
| Font & ikon | **Plus Jakarta Sans** (`next/font/google`, `--font-jakarta`), **Material Symbols Outlined** via `<link>` di `layout.tsx` (tidak ada di `next/font`), komponen `<Icon name="…" />`; `lang="id"` |
| Tema | Terang / gelap / ikut sistem — skrip di `<head>` pasang `data-theme` sebelum render (anti-kedip), tombol di footer sidebar, `localStorage.theme` |
| Chart | **Recharts**; warna dibaca dari CSS var lewat `useThemeColors()` (`src/lib/theme.ts`) |
| Export | endpoint backend `accounts/export.{xlsx,csv,json}` (tombol unduh di halaman Accounts) |
| Data | Tidak ada DB di web; semua lewat **FastAPI** (`API_BASE_URL`, di compose `http://backend:8000`) |
| Auth | Cookie sesi HMAC-SHA256 sendiri (`kurma_session`, 7 hari, Web Crypto → edge-safe) — tanpa NextAuth. Admin awal dari env (`DASHBOARD_USER`/`DASHBOARD_PASSWORD`), user tambahan di tabel `users` backend (scrypt) |
| Realtime | **Polling** dari client component (settings/logs 10 dtk, log run 5 dtk); tanpa websocket |
| Runtime | Docker multi-stage `node:22-alpine` (deps → build → runner `server.js`), `docker compose` (`kling-webapp`, port host `127.0.0.1:${DASHBOARD_PORT:-3201}` → 3000) |
| Lint/tipe | `tsc --noEmit`, `next lint` (belum ada config ESLint) |

## 2. Struktur & konvensi

```
webapp/
  src/app/
    layout.tsx            # font, <link> Material Symbols, skrip tema, <body>
    globals.css           # token + kelas design-system
    login/page.tsx        # server component, form POST /api/auth/login
    (app)/layout.tsx      # verifySession + GET /summary → <Shell>
    (app)/…/page.tsx      # / accounts settings (tab Umum) settings/logs settings/logs/[id] settings/users
    api/auth/{login,logout}/route.ts
    api/backend/[...path]/route.ts   # proxy ke FastAPI (dilindungi middleware)
    api/users[/id]/route.ts          # CRUD user dashboard
  src/components/
    Shell, Sidebar, Topbar, ThemeToggle, nav.ts   # NAV_SECTIONS (Operasi/Sistem) + pageMeta(path) → judul/subjudul topbar
    ui.tsx      # Card, Button, IconButton, Pill, StatusDot, Metric(s), Avatar, TableWrap, KV, PageBar, Loading, Delta, Progress
    form.tsx    # Field, Select, Switch, Checkbox, Fieldset
    Alert.tsx (+FlashMsg), Dialog.tsx (Dialog, ConfirmProvider, useConfirm), Empty, Icon, bits (FilterChip)
    TrendChart (akun/hari), LogView, RunNowButton (dialog jumlah/worker), StopRunButton, AccountDialog (+StatusPill)
  src/lib/  api.ts (klien + tipe), auth.ts, usersServer.ts, format.ts, theme.ts
  src/middleware.ts       # gerbang sesi; PUBLIC = /login, /api/auth/*
  public/logo/
```

- **Halaman**: server component bila hanya baca (`dashboard`, `settings/logs/[id]`); interaktif pakai `"use client"` + `apiGet` ke proxy `/api/backend/*`. `useSearchParams` wajib di dalam `<Suspense>`.
- **Judul halaman** tampil di topbar (statis dari `nav.ts`), bukan di konten. `PageBar` hanya untuk meta + aksi; nama dinamis (email akun, Run #) jadi `card-title` kartu pertama / judul dialog.
- **Kartu**: `<Card title desc actions>` → `card-head`; aksi simpan di `card-actions` (Batal outlined, utama primary). Tabel: `<TableWrap minWidth>` + `<th>/<td>` polos (gaya global), angka `className="tr tnum"`.
- **Status**: `Pill tone="success|warn|err|info|violet|neutral"`; notifikasi inline `<Alert tone>` (bukan toast); konfirmasi aksi berbahaya `useConfirm()` (native `<dialog>`), **bukan** `window.confirm`.
- **Warna**: hanya token (`text-text2`, `bg-paper`, `border-divider`, `text-err`, …). Alpha modifier (`bg-x/10`) tidak berlaku untuk `var()`; pakai `state-hover`, `nav-hover`, `backdrop`. 
- **API route**: respons error `{ error }` + status benar (401 dari middleware untuk `/api/*`). Komentar kode Bahasa Indonesia.
- **Middleware (edge)**: hanya Web Crypto; cek tanda tangan cookie + `sessionUserActive` (user dihapus → sesi mati).

## 3. Env

| Var | Keterangan |
|---|---|
| `AUTH_SECRET` | kunci HMAC cookie sesi (wajib) |
| `DASHBOARD_USER` / `DASHBOARD_PASSWORD` | admin env (fallback saat tabel users kosong); isi via `bash deploy/init-user.sh` |
| `API_BASE_URL` | base FastAPI untuk server component (default `http://localhost:8000`; compose `http://backend:8000`). Client selalu lewat `/api/backend` |
| `DASHBOARD_PORT` | port host (default 3201) |

## 4. Jalankan & deploy

```bash
cd webapp && npm install
npm run dev                      # http://localhost:3000 (butuh backend di :8000)
npx tsc --noEmit && npm run build
# produksi (di VPS, dari root repo):
git pull && docker compose up -d --build webapp
```

Verifikasi sebelum bilang selesai: `npx tsc --noEmit` + `npm run build`.

## 5. Jebakan yang sudah pernah kena

1. `page.tsx` hanya boleh `export default` + field Next (`metadata`, `dynamic`); helper bersama taruh di `src/components/bits.tsx`.
2. `Material_Symbols_Outlined` tidak ada di `next/font/google` (Next 15.1) → pakai `<link>` dengan `display=block` supaya ligature tidak berkedip; butuh jaringan saat runtime.
3. Kelas yang dirakit dinamis (`pill-${tone}`) tidak masuk `@layer components` Tailwind (ter-purge); karena itu kelas design-system ditulis sebagai CSS biasa, bukan di `@layer`.
4. Recharts butuh hex literal → baca `getComputedStyle` + `MutationObserver` `data-theme`; chart render satu frame setelah mount.
5. `useSearchParams` di luar `<Suspense>` memecahkan build.
6. `NEXT_PUBLIC_*` di-inline saat build → set di stage build Dockerfile, bukan hanya runtime.
