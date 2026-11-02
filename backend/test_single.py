#!/usr/bin/env python3
"""
test_single.py — uji satu akun (tanpa retry, tanpa simpan ke DB kecuali --save).

  python test_single.py                         # email dibuat otomatis dari provider
  python test_single.py --mode 1secmail
  python test_single.py user_x1@domainku.biz.id --mode webhook
"""
import argparse
import asyncio
import sys

import core.bootstrap  # noqa: F401
from core import config
from core.log import ok, err, info


class _FixedEmail:
    """MailClient minimal untuk email yang ditentukan user (OTP via webhook/local_tempmail)."""

    def __init__(self, email: str, mode: str):
        from core.mail import PROVIDERS
        self._inner = PROVIDERS[mode]()
        self._inner.email = email
        self.email, self.mode, self.extra = email, mode, {}

    @property
    def domain(self): return self.email.split("@")[-1]
    def poll_otp(self, timeout=None): return self._inner.poll_otp(timeout)
    def poll_link(self, timeout=None, url_patterns=None): return self._inner.poll_link(timeout, url_patterns)
    def poll_message(self, timeout): return self._inner.poll_message(timeout)


async def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    p = argparse.ArgumentParser(description=f"Test single {config.SITE_NAME} account creation")
    p.add_argument("email", nargs="?", help="Email yang sudah ada (butuh --mode webhook/local_tempmail). Kosong = generate.")
    p.add_argument("--mode", choices=["webhook", "local_tempmail", "1secmail", "mailtm", "gptmail"])
    p.add_argument("--save", action="store_true", help="Simpan hasil ke DB + results file")
    args = p.parse_args()

    for pr in config.validate(require_password=True):
        err(pr)
    mode = args.mode or ("webhook" if config.CLOUDFLARE_WORKER_URL and config.CUSTOM_DOMAINS else config.EMAIL_PROVIDER)

    from core.mail import make_mail_client
    from core.runner import create_one

    if args.email:
        if mode not in ("webhook", "local_tempmail"):
            err("Email manual hanya untuk --mode webhook/local_tempmail"); return 2
        client = _FixedEmail(args.email.strip(), mode)
    else:
        client = make_mail_client(mode)
        if client is None:
            err("Tidak ada provider email tersedia"); return 2

    print("=" * 60); print(f"  Uji akun tunggal: {client.email} | mode {client.mode}"); print("=" * 60)
    res = await create_one(client)

    print("\n" + "=" * 60); print("  HASIL"); print("=" * 60)
    if res.success:
        ok("SUKSES"); info(f"Email: {res.email} | Password: {res.password} | User ID: {res.user_id}")
    else:
        err(f"GAGAL — {res.error}")
    if args.save and res.email:
        import db
        from models import init_db
        from core.results import db_insert_account, save_result
        engine = db.get_engine(); init_db(engine)
        db_insert_account(engine, res.to_dict(), None); save_result("test", res.to_dict())
    return 0 if res.success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
