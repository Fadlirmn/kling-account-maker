#!/bin/bash
# entrypoint.sh — camoufox fetch (jika belum), Xvfb :99, patch Playwright, cek GeoIP, lalu exec "$@"
# Default CMD (Dockerfile): uvicorn api:app. Creator on-demand: compose profile "creator".
# Dibutuhkan di lingkungan Docker dimana headless Firefox
# masih membutuhkan DISPLAY untuk inisialisasi OpenGL/WebGL context

set -e

parse_proxy() {
    local raw_proxy="$1"
    raw_proxy=$(echo "$raw_proxy" | tr -d '\r' | xargs)
    if [ -z "$raw_proxy" ]; then
        return
    fi
    
    if [[ "$raw_proxy" =~ ^[a-zA-Z0-9]+:// ]]; then
        echo "$raw_proxy"
        return
    fi
    
    if [[ "$raw_proxy" == *@* ]]; then
        echo "http://$raw_proxy"
        return
    fi
    
    IFS=':' read -r -a parts <<< "$raw_proxy"
    if [ ${#parts[@]} -eq 4 ]; then
        if [[ "${parts[1]}" =~ ^[0-9]+$ ]]; then
            echo "http://${parts[2]}:${parts[3]}@${parts[0]}:${parts[1]}"
        else
            echo "http://${parts[0]}:${parts[1]}@${parts[2]}:${parts[3]}"
        fi
    elif [ ${#parts[@]} -eq 2 ]; then
        echo "http://${parts[0]}:${parts[1]}"
    else
        echo "http://$raw_proxy"
    fi
}

# Cek apakah camoufox browser sudah terinstall
if ! python3 -c "from camoufox.pkgman import launch_path; launch_path()" 2>/dev/null; then
    echo "⏳ camoufox browser belum terinstall, mendownload..."
    
    if [ -z "$HTTPS_PROXY" ]; then
        RAW_PROXY=""
        if [ -f "data/proxy.txt" ]; then
            echo "ℹ️ Membaca proxy dari data/proxy.txt..."
            RAW_PROXY=$(head -n 1 data/proxy.txt)
        elif [ -f "proxy.txt" ]; then
            echo "ℹ️ Membaca proxy dari proxy.txt..."
            RAW_PROXY=$(head -n 1 proxy.txt)
        elif [ -f ".env" ]; then
            echo "ℹ️ Membaca PROXY_LIST dari .env..."
            RAW_PROXY=$(grep "PROXY_LIST=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" | cut -d',' -f1 | tr -d '\r')
        fi
        
        if [ -n "$RAW_PROXY" ]; then
            ENV_PROXY=$(parse_proxy "$RAW_PROXY")
            if [ -n "$ENV_PROXY" ]; then
                echo "ℹ️ Menggunakan proxy untuk download: $ENV_PROXY"
                export HTTPS_PROXY="$ENV_PROXY"
                export HTTP_PROXY="$ENV_PROXY"
            fi
        fi
    fi

    python3 -m camoufox fetch
    echo "✅ camoufox browser terinstall."
fi

# Start Xvfb virtual display di background
if command -v Xvfb >/dev/null 2>&1; then
    echo "🖥️  Starting Xvfb virtual display :99..."
    rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 || true
    
    Xvfb :99 -screen 0 1920x1080x24 -ac > /tmp/xvfb.log 2>&1 &
    XVFB_PID=$!
    export DISPLAY=:99
    sleep 2
    
    if kill -0 $XVFB_PID 2>/dev/null; then
        echo "✅ Xvfb started successfully (PID: $XVFB_PID)"
    else
        echo "❌ Xvfb FAILED to start! Menampilkan log:"
        cat /tmp/xvfb.log
        echo "⚠️  Melanjutkan menggunakan headless mode..."
        unset DISPLAY
    fi
fi

# Patch playwright Firefox driver
if [ -f "scripts/patch_playwright.sh" ]; then
    echo "🩹 Patching Playwright Firefox driver..."
    bash scripts/patch_playwright.sh /usr/local || echo "⚠️ Playwright patch failed"
fi

# Pre-download GeoIP database
echo "🌍 Checking GeoIP database..."
python3 -c "
import os, sys
from camoufox.locale import MMDB_FILE, download_mmdb
try:
    import geoip2.database
    if os.path.exists(MMDB_FILE) and os.path.getsize(MMDB_FILE) > 0:
        with geoip2.database.Reader(str(MMDB_FILE)) as r:
            print('🌍 [GeoIP] MMDB is valid. Skipping download.')
            sys.exit(0)
except Exception as e:
    print('🌍 [GeoIP] MMDB check failed:', e)
print('🌍 [GeoIP] Downloading/updating MMDB...')
try:
    download_mmdb()
    print('🌍 [GeoIP] MMDB download complete.')
except Exception as e:
    print('🌍 [GeoIP] Download failed:', e)
    sys.exit(1)
" || echo "⚠️ Warning: Failed to pre-download GeoIP database"

echo "🚀 Starting Kling Account Maker: $*"
exec "$@"
