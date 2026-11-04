r"""
sites.kling.flow — langkah-langkah di halaman kling.ai.

Implementasi draft pertama dari riset manual (Playwright Codegen, 2026-11-03) ke
https://kling.ai/app. BELUM divalidasi end-to-end dengan OTP asli (codegen cuma pakai kode
dummy "123456") — AUTH_COOKIE/LOGGED_IN_URL_KW di selectors.py masih kosong. Jalankan sekali
secara manual/terawasi (MANUAL_OTP=true, 1 worker) sebelum dipercaya buat run otomatis/bulk.

Kontrak dengan core.runner:
  - `page`, `ctx` sudah di-launch (proxy + routing hemat bandwidth) oleh core.browser.BrowserSession.
  - `mail_client` (core.mail.base.MailClient) sudah punya `.email`; OTP diambil blocking →
        otp = await asyncio.to_thread(mail_client.poll_otp, config.OTP_TIMEOUT)
  - Kembalikan AccountResult(success=True, status="standby", user_id=..., otp=..., cookies=await ctx.cookies()).
  - Sinyal masalah dengan raise (runner yang blacklist/retry):
        DomainBlocked(domain)     → site menolak domain email
        ProxyFlagged("cloudflare")→ IP di-flag / captcha / redirect aneh
        OtpTimeout()              → OTP tidak datang
        FormNotFound("email input") → elemen wajib tidak ada
  - Jangan sentuh proxy/domain blacklist langsung.
  - Helper generik: core.ui_helpers (dismiss_cookie_banner, click_first, fill_first, fill_otp,
    manual_otp_prompt), core.browser.save_debug_screenshot(page, email, "step").
"""
import asyncio

from core import config
from core.runner import AccountResult, DomainBlocked, ProxyFlagged, OtpTimeout, FormNotFound
from core.ui_helpers import dismiss_cookie_banner, click_first, fill_first, fill_otp, manual_otp_prompt
from core.browser import save_debug_screenshot
from sites.kling import selectors as S

SITE_NAME = "kling"
IS_STUB = False        # implementasi draft pertama — lihat catatan di atas sebelum dipakai bulk
ALLOW_POPUPS = False   # alur signup via S.SIGNUP_URL_DEFAULT (/app) tidak butuh popup


async def create_account(page, ctx, email: str, password: str, mail_client, log) -> AccountResult:
    url = config.KLING_SIGNUP_URL or S.SIGNUP_URL_DEFAULT
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await dismiss_cookie_banner(page)

    content = await page.content()
    if any(kw in content for kw in S.CLOUDFLARE_KW):
        await save_debug_screenshot(page, email, "cloudflare")
        raise ProxyFlagged("cloudflare")

    if not await click_first(page, S.SIGNIN_OPEN_BTN):
        await save_debug_screenshot(page, email, "signin-open-not-found")
        raise FormNotFound("sign in button")

    if not await click_first(page, S.SIGNUP_EMAIL_BTN):
        await save_debug_screenshot(page, email, "continue-with-email-not-found")
        raise FormNotFound("continue with email button")

    if not await fill_first(page, S.EMAIL_INPUT, email):
        await save_debug_screenshot(page, email, "email-input-not-found")
        raise FormNotFound("email input")
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(800)

    if S.DOMAIN_REJECTED_KW:
        content = await page.content()
        if any(kw in content for kw in S.DOMAIN_REJECTED_KW):
            raise DomainBlocked(mail_client.domain)

    # Muncul kalau email belum terdaftar; no-op (abaikan) kalau sudah di alur signup.
    await click_first(page, S.SIGNUP_CONFIRM_BTN)

    if not await fill_first(page, S.PASSWORD_INPUT, password):
        await save_debug_screenshot(page, email, "password-input-not-found")
        raise FormNotFound("password input")
    if not await fill_first(page, S.CONFIRM_PASSWORD_INPUT, password):
        raise FormNotFound("confirm password input")
    if not await click_first(page, S.SUBMIT_BTN):
        await save_debug_screenshot(page, email, "next-step-not-found")
        raise FormNotFound("next step button")
    await page.wait_for_timeout(1500)

    # Server kadang menolak password lemah & merender ulang step yang sama — retry sekali.
    pw_field = page.locator(S.PASSWORD_INPUT[0]).first
    if await pw_field.count() and await pw_field.is_visible():
        await fill_first(page, S.PASSWORD_INPUT, password)
        await fill_first(page, S.CONFIRM_PASSWORD_INPUT, password)
        await click_first(page, S.SUBMIT_BTN)
        await page.wait_for_timeout(1500)

    otp = await asyncio.to_thread(mail_client.poll_otp, config.OTP_TIMEOUT)
    if not otp:
        otp = manual_otp_prompt()
    if not otp:
        await save_debug_screenshot(page, email, "otp-timeout")
        raise OtpTimeout()

    if not await fill_otp(page, otp):
        await save_debug_screenshot(page, email, "otp-input-not-found")
        raise FormNotFound("otp input")
    if not await click_first(page, S.OTP_SUBMIT_BTN):
        await save_debug_screenshot(page, email, "otp-submit-not-found")
        raise FormNotFound("otp submit button")
    await page.wait_for_timeout(2000)

    cookies = await ctx.cookies()
    user_id = next((c["value"] for c in cookies if c["name"] == S.AUTH_COOKIE), "") if S.AUTH_COOKIE else ""
    if S.LOGGED_IN_URL_KW and not any(kw in page.url for kw in S.LOGGED_IN_URL_KW):
        await save_debug_screenshot(page, email, "login-not-confirmed")

    return AccountResult(email=email, password=password, success=True, status="standby",
                          user_id=user_id, otp=otp, cookies=cookies)
