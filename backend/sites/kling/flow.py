r"""
sites.kling.flow — langkah-langkah di halaman kling.ai. STUB — belum diimplementasi.

Kontrak dengan core.runner:
  - `page`, `ctx` sudah di-launch (proxy + routing hemat bandwidth) oleh core.browser.BrowserSession.
  - `mail_client` (core.mail.base.MailClient) sudah punya `.email`; OTP diambil blocking →
        otp = await asyncio.to_thread(mail_client.poll_otp, config.OTP_TIMEOUT)
    atau link verifikasi:
        link = await asyncio.to_thread(mail_client.poll_link, config.OTP_TIMEOUT, [r"https://\S*kling\S*verify\S*"])
  - Kembalikan AccountResult(success=True, status="standby", user_id=..., otp=..., cookies=await ctx.cookies()).
  - Sinyal masalah dengan raise (runner yang blacklist/retry):
        DomainBlocked(domain)     → site menolak domain email
        ProxyFlagged("cloudflare")→ IP di-flag / captcha / redirect aneh
        OtpTimeout()              → OTP tidak datang
        FormNotFound("email input") → elemen wajib tidak ada
  - Jangan sentuh proxy/domain blacklist langsung.
  - Helper generik: core.ui_helpers (dismiss_cookie_banner, type_react_safe, fill_otp, manual_otp_prompt),
    core.browser.save_debug_screenshot(page, email, "step").

TODO: riset halaman signup kling.ai (email+password? phone? Google?), isi selectors.py, implementasi di bawah.
"""
import asyncio  # noqa: F401  (dipakai saat implementasi)

from core import config  # noqa: F401
from core.runner import AccountResult, DomainBlocked, ProxyFlagged, OtpTimeout, FormNotFound  # noqa: F401
from core.ui_helpers import dismiss_cookie_banner, fill_otp, type_react_safe, manual_otp_prompt  # noqa: F401
from core.browser import save_debug_screenshot  # noqa: F401
from sites.kling import selectors as S  # noqa: F401

SITE_NAME = "kling"
IS_STUB = True         # hapus/False setelah flow nyata diimplementasi (dipakai api.health flow_implemented)
ALLOW_POPUPS = False   # True hanya jika signup butuh popup OAuth


async def create_account(page, ctx, email: str, password: str, mail_client, log) -> AccountResult:
    """
    TODO implementasi (urutan yang disarankan, mirip flow sumber):
      1. await page.goto(config.KLING_SIGNUP_URL, wait_until="domcontentloaded", timeout=60000)
         - deteksi Cloudflare/captcha → raise ProxyFlagged("cloudflare")
      2. await dismiss_cookie_banner(page)
      3. klik tombol "Sign up with email" (S.SIGNUP_EMAIL_BTN) → raise FormNotFound("email button")
      4. isi email (S.EMAIL_INPUT) + password (S.PASSWORD_INPUT) → submit
         - pesan domain ditolak → raise DomainBlocked(mail_client.domain)
      5. otp = await asyncio.to_thread(mail_client.poll_otp, config.OTP_TIMEOUT)
         - kosong → otp = manual_otp_prompt() ; masih kosong → raise OtpTimeout()
      6. await fill_otp(page, otp) ; submit jika perlu
      7. verifikasi login (URL mengandung S.LOGGED_IN_URL_KW / cookie S.AUTH_COOKIE)
      8. user_id dari cookie/API; cookies = await ctx.cookies()
      9. return AccountResult(email=email, password=password, success=True, status="standby",
                              user_id=user_id, otp=otp, cookies=cookies)
    """
    raise NotImplementedError("sites/kling/flow.py: flow signup kling.ai belum dibuat (TODO)")
