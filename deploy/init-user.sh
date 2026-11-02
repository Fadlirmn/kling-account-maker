#!/usr/bin/env bash
# Set user login dashboard + AUTH_SECRET di .env (buat baris kalau belum ada).
#   bash deploy/init-user.sh <user> <password>
# AUTH_SECRET hanya dibuat kalau belum ada/masih placeholder (mengganti = semua session logout).
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -ge 2 ] || { echo "pakai: bash deploy/init-user.sh <user> <password>"; exit 1; }
USER_="$1"; PASS="$2"
[ -f .env ] || cp .env.example .env
setkv() {  # setkv KEY VALUE — ganti baris atau tambah
  if grep -q "^$1=" .env; then
    python3 - "$1" "$2" <<'PY'
import sys,pathlib
k,v=sys.argv[1],sys.argv[2]; p=pathlib.Path(".env")
p.write_text("\n".join(f"{k}={v}" if l.startswith(k+"=") else l for l in p.read_text().splitlines())+"\n")
PY
  else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
case "$PASS$USER_" in *[[:cntrl:]]*|*$'\n'*) echo "user/password tidak boleh ada karakter kontrol"; exit 1;; esac
setkv DASHBOARD_USER "$USER_"
setkv DASHBOARD_PASSWORD "$PASS"
cur=$(grep -E '^AUTH_SECRET=' .env | cut -d= -f2- || true)
if [ ${#cur} -lt 32 ] || echo "$cur" | grep -q "YOUR_"; then
  setkv AUTH_SECRET "$(openssl rand -hex 32)"; echo "AUTH_SECRET baru dibuat"
fi
chmod 600 .env
echo "OK: admin cadangan DASHBOARD_USER=$USER_ (password tersimpan di .env). User lain: Settings ▸ User di dashboard"
echo "Terapkan: docker compose up -d webapp"
