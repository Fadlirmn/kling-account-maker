#!/bin/bash
# patch_playwright.sh — Fix known Playwright Firefox bug
# Bug: ValidationError: location.url: expected string, got undefined
# Fix: Add optional chaining + fallback values pada pageError.location properties
#
# Jalankan setelah: pip install playwright
# Usage: bash patch_playwright.sh [path_to_venv]
#
# STRATEGI RESET: selalu restore dari .bak (bukan global sed) agar aman

VENV="${1:-.venv}"
BUNDLE="$VENV/lib/python3.10/site-packages/playwright/driver/package/lib/coreBundle.js"

# Coba python3.11 juga
if [ ! -f "$BUNDLE" ]; then
    BUNDLE="$VENV/lib/python3.11/site-packages/playwright/driver/package/lib/coreBundle.js"
fi
if [ ! -f "$BUNDLE" ]; then
    BUNDLE=$(find "$VENV" -name "coreBundle.js" 2>/dev/null | head -1)
fi

if [ ! -f "$BUNDLE" ]; then
    echo "❌ coreBundle.js tidak ditemukan di $VENV"
    echo "   Pastikan playwright sudah terinstall: pip install playwright"
    exit 1
fi

echo "📄 File: $BUNDLE"

# ── Buat backup jika belum ada ──────────────────────────────────────────────
# Backup HARUS dibuat dari file yang belum di-patch (file asli)
if [ ! -f "${BUNDLE}.bak" ]; then
    cp "$BUNDLE" "${BUNDLE}.bak"
    echo "💾 Backup dibuat: ${BUNDLE}.bak"
fi

# ── Cek apakah sudah di-patch dengan versi terbaru ──────────────────────────
if grep -q 'pageError\.location?\.url || ""' "$BUNDLE"; then
    echo "✅ Sudah di-patch (versi terbaru), skip."
    exit 0
fi

# ── Reset ke kondisi asli dari backup ────────────────────────────────────────
# PENTING: jangan gunakan global sed — cukup restore dari .bak yang bersih
echo "🔄 Restoring dari backup (file asli yang bersih)..."
cp "${BUNDLE}.bak" "$BUNDLE"

# Verifikasi restore berhasil (file harus mengandung pattern asli)
if ! grep -q 'pageError\.location\.url' "$BUNDLE"; then
    echo "❌ Backup mungkin sudah korup. Reinstall playwright:"
    echo "   pip install --force-reinstall playwright"
    echo "   Lahu hapus ${BUNDLE}.bak dan jalankan script ini lagi."
    exit 1
fi

# ── Apply patch (targeted — HANYA pada pageError.location) ──────────────────
sed -i 's/pageError\.location\.url/pageError.location?.url || ""/g' "$BUNDLE"
sed -i 's/pageError\.location\.lineNumber/pageError.location?.lineNumber || 0/g' "$BUNDLE"
sed -i 's/pageError\.location\.columnNumber/pageError.location?.columnNumber || 0/g' "$BUNDLE"

# ── Verifikasi ───────────────────────────────────────────────────────────────
if grep -q 'pageError\.location?\.url || ""' "$BUNDLE"; then
    echo "✅ Patch berhasil!"
    grep -n "pageError.location" "$BUNDLE" | head -10
else
    echo "❌ Patch gagal — restore backup"
    cp "${BUNDLE}.bak" "$BUNDLE"
    exit 1
fi
