#!/usr/bin/env python3
"""
download_geoip.py — Download and validate MaxMind GeoIP database for Camoufox.
"""
import os
import sys
import urllib.request
from pathlib import Path

# Bypass Camoufox version checks
try:
    from camoufox import pkgman as _cfpkg
    _cfpkg.Version.is_supported = lambda self: True
except Exception:
    pass

from camoufox.locale import download_mmdb, MMDB_FILE

def validate_mmdb(file_path: str) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    try:
        import geoip2.database
        with geoip2.database.Reader(file_path) as r:
            # Try a dummy lookup to make sure it's fully valid
            r.city("8.8.8.8")
            return True
    except Exception:
        return False

# 1. Validasi awal: Jika sudah valid, skip download!
if validate_mmdb(str(MMDB_FILE)):
    print(f"[GeoIP] MMDB already exists and is valid: {MMDB_FILE}. Skipping download.")
    sys.exit(0)

print("[GeoIP] MMDB is missing or invalid. Initiating download...")

# Buat parent directory jika belum ada
Path(MMDB_FILE).parent.mkdir(parents=True, exist_ok=True)

# 2. Coba unduh dari direct mirror CDN (lebih cepat dan stabil dari GitHub API)
direct_url = "https://raw.githubusercontent.com/P3TERX/GeoLite.mmdb/download/GeoLite2-City.mmdb"
print(f"[GeoIP] Downloading from fast CDN mirror: {direct_url}")

success = False
try:
    # Buat request dengan custom User-Agent dan timeout
    req = urllib.request.Request(
        direct_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=30) as response, open(MMDB_FILE, 'wb') as out_file:
        length = response.getheader('content-length')
        if length:
            total_size = int(length)
            downloaded = 0
            block_size = 1024 * 64
            print(f"[GeoIP] File size: {total_size / 1024 / 1024:.2f} MB")
            
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                # Tampilkan progress sederhana
                percent = int(100 * downloaded / total_size)
                sys.stdout.write(f"\r[GeoIP] Progress: {percent}% ({downloaded / 1024 / 1024:.2f}MB / {total_size / 1024 / 1024:.2f}MB)")
                sys.stdout.flush()
            print()
        else:
            out_file.write(response.read())
        
    if validate_mmdb(str(MMDB_FILE)):
        print(f"[GeoIP] Mirror download success and validated: {MMDB_FILE}")
        success = True
except Exception as e:
    print(f"\n[GeoIP] Mirror download failed: {e}")
    Path(MMDB_FILE).unlink(missing_ok=True)

# 3. Fallback ke download_mmdb() default bawaan camoufox jika direct mirror gagal
if not success:
    print("[GeoIP] Running default camoufox download_mmdb() fallback...")
    try:
        download_mmdb()
        if validate_mmdb(str(MMDB_FILE)):
            print(f"[GeoIP] Default fallback download success: {MMDB_FILE}")
            success = True
    except Exception as e:
        print(f"[GeoIP] Default fallback download failed: {e}")

if not success:
    print("[GeoIP] Error: All GeoIP download attempts failed.")
    sys.exit(1)
