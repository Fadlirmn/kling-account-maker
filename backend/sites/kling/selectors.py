"""
sites.kling.selectors — konstanta selector/URL/keyword halaman kling.ai.
SEMUA masih TODO; diisi setelah riset halaman signup.
"""
# TODO: URL fallback jika KLING_SIGNUP_URL env kosong
SIGNUP_URL_DEFAULT = ""

# TODO: tombol/link memulai signup via email
SIGNUP_EMAIL_BTN: list[str] = []            # contoh: ['button:has-text("Sign up with email")']

# TODO: input form
EMAIL_INPUT: list[str] = []                 # contoh: ['input[type="email"]', 'input[name="email"]']
PASSWORD_INPUT: list[str] = []              # contoh: ['input[type="password"]']
SUBMIT_BTN: list[str] = []                  # contoh: ['button[type="submit"]']

# TODO: form OTP / verifikasi
OTP_FORM_KW: list[str] = []                 # teks yang menandakan halaman OTP muncul
VERIFY_BY_LINK = False                      # True jika Kling kirim link, bukan kode

# TODO: deteksi sukses login
LOGGED_IN_URL_KW: list[str] = []            # substring URL setelah login
AUTH_COOKIE: str = ""                       # nama cookie sesi

# TODO: deteksi blokir
CLOUDFLARE_KW: list[str] = ["Checking your browser", "cf-chl", "Ray ID", "Attention Required"]
DOMAIN_REJECTED_KW: list[str] = []          # pesan error domain email tidak diterima
