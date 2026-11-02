"""
core.ui_helpers — helper interaksi halaman yang tidak spesifik site:
cookie banner, ketik React-safe, isi OTP (6 kotak / N kotak / input tunggal / last resort),
prompt OTP manual (opsional).

Diport dari engine sumber.
"""
import select
import sys

from core import config
from core.log import info, warn, ok

DEFAULT_COOKIE_TEXTS = [
    "Accept all", "Accept all cookies", "Accept cookies", "Agree and proceed", "Terima semua",
    "Accept necessary cookies only", "Allow all", "Allow cookies", "I agree",
    "Accept", "Agree", "Terima", "Close", "Tutup",
]

SINGLE_OTP_SELECTORS = [
    'input[name="otp"]', 'input[autocomplete="one-time-code"]', 'input[type="number"]',
    'input[inputmode="numeric"]', f'input[maxlength="{config.OTP_LENGTH}"]', 'input[maxlength="8"]',
    'input[data-testid*="otp"]', 'input[data-testid*="code"]', 'input[placeholder*="code" i]',
    'input[aria-label*="code" i]', 'input[type="text"]', 'input[type="tel"]',
]


async def dismiss_cookie_banner(page, texts: list[str] = None, wait_ms: int = 1500) -> bool:
    """Klik tombol consent pertama yang terlihat. True jika ada yang diklik."""
    for txt in texts or DEFAULT_COOKIE_TEXTS:
        try:
            btn = page.get_by_role("button", name=txt, exact=False)
            if await btn.count() and await btn.first.is_visible():
                await btn.first.click(timeout=4000, force=True)
                info(f"Cookie banner ditutup: '{txt}'")
                await page.wait_for_timeout(wait_ms)
                return True
        except Exception:
            continue
    return False


async def type_react_safe(page, locator, text: str, delay: int = 80) -> bool:
    """Ketik karakter per karakter + dispatch event agar state React terpicu."""
    try:
        await locator.click(timeout=3000)
        await locator.evaluate("el => el.value = ''")
        try:
            await locator.press_sequentially(text, delay=delay)
        except AttributeError:
            for ch in text:
                await locator.press(ch)
                await page.wait_for_timeout(60)
        await locator.evaluate("""el => {
            el.dispatchEvent(new Event('input',  {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: 'Enter'}));
        }""")
        return True
    except Exception as e:
        warn(f"type_react_safe gagal: {e}")
        return False


async def _fill_boxes(page, boxes, otp: str, n: int) -> bool:
    try:
        for i, digit in enumerate(otp[:n]):
            box = boxes.nth(i)
            await box.click(timeout=3000)
            try:
                await box.press_sequentially(digit, delay=60)
            except AttributeError:
                await page.keyboard.type(digit, delay=60)
            await box.evaluate("el => el.dispatchEvent(new Event('input', {bubbles:true}))")
            await page.wait_for_timeout(80)
        return True
    except Exception as e:
        warn(f"Gagal ketik OTP via kotak: {e} — fallback fill()")
        try:
            for i, digit in enumerate(otp[:n]):
                await boxes.nth(i).fill(digit)
                await page.wait_for_timeout(80)
            return True
        except Exception as e2:
            warn(f"Fallback fill kotak gagal: {e2}")
            return False


async def fill_otp(page, otp: str, settle_ms: int = 1500) -> bool:
    """
    Strategi berurutan:
      1. N kotak input[maxlength="1"] (N = len OTP)
      2. ≥4 kotak (variasi 4-5 digit)
      3. input tunggal (SINGLE_OTP_SELECTORS)
      4. last resort: input visible apapun selain email/hidden
    """
    boxes = page.locator('input[maxlength="1"]')
    count = await boxes.count()
    info(f"OTP boxes: {count} kotak | URL: {page.url[:80]}")
    filled = False

    if count >= len(otp):
        filled = await _fill_boxes(page, boxes, otp, len(otp))
        if filled: info(f"OTP diisi via {len(otp)} kotak individual")
    elif count >= 4:
        filled = await _fill_boxes(page, boxes, otp, count)
        if filled: info(f"OTP diisi via {count} kotak individual")

    if not filled:
        for sel in SINGLE_OTP_SELECTORS:
            el = page.locator(sel)
            try:
                if await el.count() and await el.first.is_visible():
                    if await type_react_safe(page, el.first, otp):
                        info(f"OTP diisi via input tunggal: {sel}")
                        filled = True
                        break
            except Exception:
                continue

    if not filled:
        warn("Tidak ada input OTP dikenali — coba semua input visible...")
        inputs = page.locator("input:visible")
        for i in range(await inputs.count()):
            inp = inputs.nth(i)
            t = (await inp.get_attribute("type") or "").lower()
            nm = (await inp.get_attribute("name") or "").lower()
            if t in ("hidden", "checkbox", "radio", "submit", "button", "email", "password") or nm == "email":
                continue
            if await type_react_safe(page, inp, otp):
                info(f"OTP diisi via last-resort input (type={t}, name={nm})")
                filled = True
                break

    await page.wait_for_timeout(settle_ms)
    return filled


def manual_otp_prompt(timeout: int = 60, label: str = "OTP") -> str:
    """Baca OTP dari stdin (blocking, pakai select). Hanya dipanggil jika MANUAL_OTP=true."""
    if not config.MANUAL_OTP:
        return ""
    try:
        info(f"Menunggu input {label} manual di terminal... ({timeout}s)")
        print(f"Masukkan {label}: ", end="", flush=True)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            val = sys.stdin.readline().strip()
            if val:
                ok(f"Menggunakan {label} manual: {val}")
                return val
    except Exception as e:
        warn(f"Gagal baca input manual: {e}")
    print()
    return ""
