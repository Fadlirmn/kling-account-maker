"""core.results — simpan hasil ke results_kling.txt + cookies/<email>.json + DB (repo.upsert_account)."""
from __future__ import annotations

import json
from datetime import datetime

from core import config
from core.log import mask_creds, err


def save_result(idx, result: dict) -> None:
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    status = "BERHASIL ✅" if result.get("success") else f"GAGAL ❌ ({result.get('error', '')})"
    lines = [
        "=" * 80,
        f"[{idx}] {ts} | {status}",
        f"Email     : {result.get('email', '-')}",
        f"Password  : {result.get('password', '-') or '-'}",
        f"User ID   : {result.get('user_id', '-') or '-'}",
        f"OTP       : {result.get('otp', '-') or '-'}",
        f"Mode      : {result.get('email_mode', '-') or '-'}",
        f"Proxy     : {mask_creds(result.get('proxy', '') or '-')}",
        f"Status    : {result.get('status', '-')}",
        f"Cookies   : cookies/{result.get('email', '')}.json" if result.get("cookies") else "Cookies   : -",
    ]
    for k, v in (result.get("extra") or {}).items():
        lines.append(f"{k:<10}: {v}")
    lines += ["=" * 80, ""]
    try:
        with open(config.RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        err(f"Gagal tulis results file: {e}")

    if result.get("cookies") and result.get("email"):
        try:
            cf = config.COOKIES_DIR / f"{result['email']}.json"
            cf.write_text(json.dumps(result["cookies"], indent=2), encoding="utf-8")
        except OSError as e:
            err(f"Gagal tulis cookies file: {e}")


def db_insert_account(engine, result: dict, run_id: int | None = None) -> bool:
    """Upsert hasil ke kling_accounts. proxy disimpan ter-mask."""
    try:
        import repo
        data = dict(result)
        data.setdefault("status", "standby" if result.get("success") else "failed")
        data["proxy"] = mask_creds(data.get("proxy", "") or "")
        repo.upsert_account(engine, data, run_id)
        return True
    except Exception as e:  # noqa: BLE001
        err(f"DB insert error: {e}")
        return False
