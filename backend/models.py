"""
Schema DB: pool akun Kling + riwayat run + settings dashboard + user dashboard.
Tabel dibuat otomatis lewat init_db() (SQLAlchemy metadata.create_all) — cukup
untuk PostgreSQL maupun SQLite; kolom baru pada DB lama ditambah _ensure_columns().
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Column, DateTime, ForeignKey, Index, Integer, MetaData, String, Table, Text, text,
)

from core import config

metadata = MetaData()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# satu batch pembuatan akun (manual dari dashboard/CLI, jadwal harian, atau isi ulang otomatis)
runs = Table(
    "runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trigger", String(20), nullable=False),            # manual | scheduled | auto_refill
    Column("config_version", Integer, nullable=False, default=1),
    Column("requested", Integer, nullable=False),             # slot diminta
    Column("workers", Integer, nullable=False),
    Column("provider", String(20)),                           # provider email efektif
    Column("started_at", DateTime(timezone=True), nullable=False, default=utcnow),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(20), nullable=False),             # running | success | partial | failed
    Column("created_ok", Integer, nullable=False, default=0),
    Column("failed", Integer, nullable=False, default=0),
    Column("skipped", Integer, nullable=False, default=0),    # slot dibatalkan (stop / fatal)
    Column("error_message", Text),
    Column("log", Text),                                      # seluruh baris RunLogger
)

# akun hasil pembuatan; status: pending|standby|active|exhausted|used|banned|failed
kling_accounts = Table(
    "kling_accounts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("password", Text, default=""),
    Column("user_id", String(100), default=""),
    Column("otp", String(20), default=""),
    Column("cookies", Text, default=""),                      # JSON list cookie Playwright
    Column("proxy", Text, default=""),                        # sudah di-mask (tanpa kredensial)
    Column("email_mode", String(20), default=""),
    Column("status", String(20), nullable=False, default="pending"),
    Column("attempts", Integer, default=0),
    Column("credits", String(50), default=""),
    Column("plan", String(50), default=""),
    Column("error", Text),                                    # kode error terakhir
    Column("run_id", Integer, ForeignKey("runs.id", ondelete="SET NULL")),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
    Index("ix_accounts_status", "status"),
    Index("ix_accounts_created", "created_at"),
    Index("ix_accounts_run", "run_id"),
)

# domain email yang ditolak site → tidak dipakai lagi (core.domains)
banned_domains = Table(
    "banned_domains", metadata,
    Column("domain", String(255), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
)

# konfigurasi yang bisa diubah dari dashboard (key/value JSON)
settings = Table(
    "settings", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
)

# default dari backend/config.json "defaults" (via core.config); baris tabel settings menimpa saat runtime
DEFAULT_SETTINGS: dict = {
    "workers": config.WORKERS,                          # browser paralel per run
    "batch_size": config.BATCH_SIZE,                    # slot per run terjadwal / isi ulang
    "email_provider": config.EMAIL_PROVIDER,            # webhook|local_tempmail|1secmail|mailtm|gptmail
    "max_daily_success": config.MAX_DAILY_SUCCESS,      # akun sukses maks per 24 jam
    "standby_target": config.STANDBY_TARGET,            # isi ulang otomatis sampai standby = n (0 = mati)
    "refill_interval_minutes": config.REFILL_INTERVAL_MIN,  # jeda cek isi ulang (0 = mati)
    "enable_scheduler": config.SCHEDULE_ENABLED,        # job harian aktif (config scheduler.enabled = master)
    "schedule_time": config.SCHEDULE_TIME,              # WIB
    "schedule_jitter_minutes": config.SCHEDULE_JITTER_MIN,  # jam run digeser acak 0..n menit
    "max_attempts_per_slot": config.MAX_ATTEMPTS_PER_SLOT,
    "delay_between_accounts": config.DELAY_BETWEEN_ACCOUNTS,
    "browser_concurrency": config.BROWSER_CONCURRENCY,
    "debug_screenshots": config.DEBUG_SCREENSHOTS,
    "retention_days": config.RETENTION_DAYS,            # hapus run lebih tua dari n hari (0 = simpan)
    "config_version": 1,
}

# akun dashboard tambahan; admin dari env DASHBOARD_USER tetap jadi akun cadangan
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(64), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", String(16), nullable=False, default="member"),   # admin | member
    Column("created_at", DateTime(timezone=True), nullable=False, default=utcnow),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow),
)


# kolom yang ditambahkan setelah tabel dibuat; create_all melewati tabel yang sudah ada,
# jadi ditambah manual dengan ALTER TABLE (DB SQLite di deployment persisten antar restart).
_NEW_COLUMNS: list[tuple[str, str, str]] = [
    ("kling_accounts", "run_id", "INTEGER"),
    ("kling_accounts", "error", "TEXT"),
    ("kling_accounts", "credits", "VARCHAR(50)"),
    ("kling_accounts", "plan", "VARCHAR(50)"),
    ("kling_accounts", "proxy", "TEXT"),
    ("kling_accounts", "email_mode", "VARCHAR(20)"),
    ("kling_accounts", "updated_at", "TIMESTAMP"),
    ("users", "role", "VARCHAR(16) DEFAULT 'member'"),
]


def _ensure_columns(engine) -> None:
    with engine.begin() as con:
        for table, col, coltype in _NEW_COLUMNS:
            if engine.dialect.name == "postgresql":
                cols = [r[0] for r in con.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
                ), {"t": table})]
            else:
                # nama tabel dari konstanta internal, bukan input user
                cols = [row[1] for row in con.execute(text(f'PRAGMA table_info("{table}")')).fetchall()]
            if not cols:
                continue  # tabel belum ada (create_all yang bikin, sudah lengkap)
            if col not in cols:
                con.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))


def init_db(engine) -> None:
    metadata.create_all(engine)
    _ensure_columns(engine)
