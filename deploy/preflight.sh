#!/usr/bin/env bash
# Cek semua prasyarat sebelum `docker compose up -d --build`.
#   bash deploy/preflight.sh          (jalankan dari root repo)
# Exit 1 kalau ada FAIL. WARN tidak menghentikan.
cd "$(dirname "$0")/.."
FAIL=0
ok()   { printf '  \e[32mOK\e[0m    %s\n' "$*"; }
warn() { printf '  \e[33mWARN\e[0m  %s\n' "$*"; }
fail() { printf '  \e[31mFAIL\e[0m  %s\n' "$*"; FAIL=1; }
envval() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2-; }

echo "== Tools =="
command -v docker >/dev/null && ok "docker $(docker --version | awk '{print $3}' | tr -d ,)" || fail "docker tidak ada"
docker compose version >/dev/null 2>&1 && ok "docker compose $(docker compose version --short)" || fail "docker compose plugin tidak ada"
docker info >/dev/null 2>&1 && ok "docker daemon jalan" || fail "docker daemon tidak jalan / tidak punya izin"

echo "== .env =="
if [ -f .env ]; then
  ok ".env ada"
  # baris rusak (karakter non-printable) bikin compose gagal parse
  if LC_ALL=C grep -qP '[^\x09\x20-\x7E]' .env; then fail ".env ada karakter non-printable — compose akan gagal"; else ok ".env bersih (printable)"; fi
  db=$(envval DATABASE_URL)
  if [ -z "$db" ]; then warn "DATABASE_URL kosong → pakai SQLite backend/data/kling_accounts.db";
  elif echo "$db" | grep -Eq '^postgres(ql)?://[^:]+:[^@]+@[^/]+/[^ ]+$'; then
    echo "$db" | grep -q "YOUR_" && fail "DATABASE_URL masih placeholder" || ok "DATABASE_URL format valid"
    echo "$db" | grep -q "@localhost\|@127.0.0.1" && warn "DATABASE_URL pakai localhost — dari container harus host.docker.internal"
  else fail "DATABASE_URL format salah (harus postgresql://user:pass@host:5432/db)"; fi
  port=$(envval DASHBOARD_PORT); port=${port:-3201}
  api_port=$(envval API_PORT); api_port=${api_port:-8010}
  u=$(envval DASHBOARD_USER); pw=$(envval DASHBOARD_PASSWORD); sec=$(envval AUTH_SECRET)
  if [ -z "$u" ] || [ -z "$pw" ] || echo "$pw" | grep -q "YOUR_"; then fail "DASHBOARD_USER/DASHBOARD_PASSWORD belum diisi → bash deploy/init-user.sh <user> <password>";
  else ok "login dashboard: user '$u'"; fi
  if [ ${#sec} -lt 32 ] || echo "$sec" | grep -q "YOUR_"; then fail "AUTH_SECRET kosong/pendek (<32) → bash deploy/init-user.sh"; else ok "AUTH_SECRET ada (${#sec} char)"; fi
else
  fail ".env tidak ada (cp .env.example .env)"; port=3201; api_port=8010
fi

echo "== Engine =="
cfgval() { python3 -c "import json,sys;d=json.load(open('backend/config.json'));cur=d
for k in sys.argv[1].split('.'):
    cur=cur.get(k,'') if isinstance(cur,dict) else ''
print(cur if not isinstance(cur,(list,dict)) else json.dumps(cur))" "$1" 2>/dev/null; }
if python3 -c "import json;json.load(open('backend/config.json'))" 2>/dev/null; then ok "backend/config.json valid (non-rahasia)"; else fail "backend/config.json tidak ada / JSON rusak"; fi
[ -f backend/config.local.json ] && { python3 -c "import json;json.load(open('backend/config.local.json'))" 2>/dev/null && ok "backend/config.local.json valid (override lokal)" || fail "backend/config.local.json JSON rusak"; }
kp=$(envval KLING_DEFAULT_PASSWORD)
[ -n "$kp" ] && ok "KLING_DEFAULT_PASSWORD terisi" || fail "KLING_DEFAULT_PASSWORD kosong — setiap run akan gagal 'konfigurasi tidak lengkap'"
su=$(envval KLING_SIGNUP_URL); su=${su:-$(cfgval site.signup_url)}
[ -n "$su" ] && ok "site.signup_url terisi" || warn "site.signup_url kosong (config.json) — flow sites/kling/flow.py masih stub (run berakhir NOT_IMPLEMENTED)"
if [ -s backend/GeoLite2-City.mmdb ]; then ok "backend/GeoLite2-City.mmdb ada ($(du -h backend/GeoLite2-City.mmdb | cut -f1))";
else fail "backend/GeoLite2-City.mmdb tidak ada — mount compose akan jadi directory kosong → Camoufox NS_ERROR_NET_INTERRUPT (python backend/scripts/download_geoip.py)"; fi
[ -d backend/camoufox_cache ] || mkdir -p backend/camoufox_cache
[ -w backend/camoufox_cache ] && ok "backend/camoufox_cache writable (binary browser ~1.3GB di-download saat boot pertama)" || warn "backend/camoufox_cache tidak writable (chown?)"
for d in backend/data backend/logs backend/exports backend/cookies backend/result; do
  [ -d "$d" ] || mkdir -p "$d"
  [ -w "$d" ] || warn "$d tidak writable oleh user ini (chown?)"
done
prov=$(envval EMAIL_PROVIDER); prov=${prov:-$(cfgval email.provider)}; prov=${prov:-1secmail}
case "$prov" in
  webhook)
    [ -n "$(envval CLOUDFLARE_WORKER_URL)" ] && ok "EMAIL_PROVIDER=webhook: CLOUDFLARE_WORKER_URL terisi" || fail "EMAIL_PROVIDER=webhook butuh CLOUDFLARE_WORKER_URL"
    if [ -n "$(envval CUSTOM_DOMAINS)" ] || [ "$(cfgval email.custom_domains)" != "[]" ] || grep -Eqv '^\s*(#|$)' backend/domain.txt 2>/dev/null; then ok "domain webhook ada"; else fail "provider webhook butuh email.custom_domains (config.json) atau backend/domain.txt"; fi ;;
  local_tempmail)
    [ -n "$(envval TEMPMAIL_API_URL)" ] && ok "TEMPMAIL_API_URL terisi" || fail "EMAIL_PROVIDER=local_tempmail butuh TEMPMAIL_API_URL"
    [ -n "$(envval TEMPMAIL_SECRET)" ] || warn "TEMPMAIL_SECRET kosong" ;;
  1secmail|mailtm|gptmail) ok "EMAIL_PROVIDER=$prov (publik, tanpa konfigurasi)" ;;
  *) fail "email.provider tidak dikenal: $prov" ;;
esac
if [ -z "$(envval PROXY_LIST)" ] && [ -z "$(envval CROXY_BASE_PROXY)" ] && [ ! -s backend/data/proxy.txt ]; then
  warn "tanpa proxy (PROXY_LIST / CROXY_BASE_PROXY / backend/data/proxy.txt kosong) — browser pakai IP server langsung"
else ok "proxy terkonfigurasi"; fi

echo "== Port =="
if ss -ltn 2>/dev/null | grep -q ":$port "; then
  docker ps --format '{{.Names}} {{.Ports}}' | grep -q "kling-webapp" && ok "port $port dipakai kling-webapp (sudah jalan)" || fail "port $port dipakai proses lain — ubah DASHBOARD_PORT di .env"
else ok "port $port bebas"; fi
if ss -ltn 2>/dev/null | grep -q ":$api_port "; then
  docker ps --format '{{.Names}} {{.Ports}}' | grep -q "kling-backend" && ok "port $api_port dipakai kling-backend (sudah jalan)" || fail "port $api_port dipakai proses lain — ubah API_PORT di .env"
else ok "port $api_port bebas"; fi

echo "== Compose =="
docker compose config --quiet 2>/tmp/preflight_err && ok "docker-compose.yml + .env valid" || { fail "compose config: $(head -1 /tmp/preflight_err)"; }

echo "== PostgreSQL (dari container) =="
if [ -n "${db:-}" ]; then
  pgurl=$(echo "$db" | sed -E 's|^postgres(ql)?(\+psycopg)?://|postgresql://|')
  if docker image inspect kling-maker/backend >/dev/null 2>&1; then
    out=$(timeout 25 docker compose run --rm --no-deps -T --entrypoint python backend db.py 2>&1 | tail -1)
    echo "$out" | grep -q "^OK postgresql" && ok "$out" || fail "DB tidak bisa diakses dari container: ${out:-timeout} → cek deploy/setup-postgres.sh"
  else
    out=$(timeout 40 docker run --rm --add-host host.docker.internal:host-gateway -e PGCONNECT_TIMEOUT=8 \
          postgres:16-alpine psql "$pgurl" -tAc "select version()" 2>&1 | tail -1)
    echo "$out" | grep -q "^PostgreSQL" && ok "DB reachable dari container: $out" \
      || fail "DB tidak bisa diakses dari container: ${out:-timeout} → cek deploy/setup-postgres.sh (pg_hba 172.16.0.0/12, listen_addresses)"
  fi
fi

echo
[ $FAIL = 0 ] && echo "SIAP: docker compose up -d --build" || { echo "ADA FAIL — perbaiki dulu."; exit 1; }
