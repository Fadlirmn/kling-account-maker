#!/usr/bin/env bash
# Siapkan PostgreSQL di host untuk container (idempotent).
#   sudo bash deploy/setup-postgres.sh [db] [user] [password]
# Default: kling_maker / kling / (random)
set -euo pipefail

DB="${1:-kling_maker}"
USER_="${2:-kling}"
PASS="${3:-$(openssl rand -hex 12)}"
DOCKER_NET="172.16.0.0/12"   # semua bridge network Docker (172.16–172.31)

PG_VER=$(ls /etc/postgresql | sort -V | tail -1)
HBA="/etc/postgresql/$PG_VER/main/pg_hba.conf"
CONF="/etc/postgresql/$PG_VER/main/postgresql.conf"

cd /tmp   # hindari "could not change directory" saat sudo -u postgres

# 1) role + database
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$USER_') THEN
    CREATE ROLE "$USER_" LOGIN PASSWORD '$PASS';
  ELSE
    ALTER ROLE "$USER_" WITH PASSWORD '$PASS';
  END IF;
END \$\$;
SQL
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1 \
  || sudo -u postgres createdb -O "$USER_" "$DB"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB" -c "GRANT ALL ON SCHEMA public TO \"$USER_\";"

# 2) listen di semua interface (container masuk lewat IP host)
if ! grep -Eq "^listen_addresses\s*=\s*'(\*|0\.0\.0\.0)'" "$CONF"; then
  sed -i "s/^#\?listen_addresses\s*=.*/listen_addresses = '*'/" "$CONF"
  NEED_RESTART=1
fi

# 3) izin pg_hba dari subnet Docker
LINE="host    $DB    $USER_    $DOCKER_NET    scram-sha-256"
grep -qF "$LINE" "$HBA" || { echo "$LINE" >> "$HBA"; NEED_RELOAD=1; }

if [ "${NEED_RESTART:-}" = 1 ]; then systemctl restart postgresql; else [ "${NEED_RELOAD:-}" = 1 ] && systemctl reload postgresql; fi

echo
echo "Selesai. Tulis di .env:"
echo "DATABASE_URL=postgresql://$USER_:$PASS@host.docker.internal:5432/$DB"
