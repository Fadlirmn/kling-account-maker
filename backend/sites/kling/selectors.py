"""
sites.kling.selectors — konstanta selector/URL/keyword halaman kling.ai.
Hasil riset manual via Playwright Codegen (2026-11-03), langsung ke https://kling.ai/app
(skip landing page + popup "Try Now"). Belum pernah divalidasi end-to-end dengan OTP asli —
anggap sebagai draft pertama, bukan final.
"""

SIGNUP_URL_DEFAULT = "https://kling.ai/app"

# Buka modal login/signup
SIGNIN_OPEN_BTN: list[str] = ['text=Sign In']

# Pilih jalur email di modal
SIGNUP_EMAIL_BTN: list[str] = ['text=Continue with email']

# Input form
EMAIL_INPUT: list[str] = ['input[placeholder="Enter Email Address"]']

# Muncul setelah email diisi (blur/Tab) kalau email belum terdaftar — klik utk lanjut signup.
# Kalau email sudah terdaftar, tombol ini tidak muncul (berarti harus login, bukan signup) —
# belum ada test case utk alur itu.
SIGNUP_CONFIRM_BTN: list[str] = ['text=Sign up for free']

PASSWORD_INPUT: list[str] = ['input[placeholder^="Password (at least 8"]']
CONFIRM_PASSWORD_INPUT: list[str] = ['input[placeholder="Confirm Password"]']
SUBMIT_BTN: list[str] = ['button:has-text("Next Step")']           # submit step email+password

# Form OTP / verifikasi — input generik "Verification Code" sudah tercover oleh
# core.ui_helpers.fill_otp() (match via `input[placeholder*="code" i]`).
OTP_FORM_KW: list[str] = ["Verification Code"]
VERIFY_BY_LINK = False

# Submit akhir setelah isi kode OTP. CATATAN: teks "Sign In" sama dengan SIGNIN_OPEN_BTN di atas —
# kalau di halaman OTP ternyata ada 2 elemen "Sign In" (nav + tombol submit), perlu diskopin lebih
# spesifik (mis. ke dalam modal/dialog) saat divalidasi live.
OTP_SUBMIT_BTN: list[str] = ['button:has-text("Sign In")']

# TODO: belum tervalidasi — codegen pakai OTP dummy "123456" jadi tidak sampai login sungguhan
LOGGED_IN_URL_KW: list[str] = []
AUTH_COOKIE: str = ""

# Deteksi blokir
CLOUDFLARE_KW: list[str] = ["Checking your browser", "cf-chl", "Ray ID", "Attention Required"]
DOMAIN_REJECTED_KW: list[str] = []   # TODO: belum ketemu kasus domain email ditolak di riset ini
