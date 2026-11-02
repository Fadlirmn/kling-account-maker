"""
Koneksi database: PostgreSQL via DATABASE_URL, fallback SQLite kalau kosong.

  DATABASE_URL=postgresql://user:pass@host:5432/kling_maker   → PostgreSQL (psycopg 3)
  DATABASE_URL=                                               → SQLite di SQLITE_PATH
                                                                (default data/kling_accounts.db;
                                                                 di Docker /data/db/kling_accounts.db)
Pakai:
  from db import get_engine
  with get_engine().connect() as con: ...
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

import core.bootstrap  # noqa: F401 — load .env (ENV_FILE / ../.env) sekali
from core import config

ROOT = Path(__file__).resolve().parent


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        # normalisasi: postgres:// → postgresql+psycopg://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    path = Path(os.getenv("SQLITE_PATH", str(config.SQLITE_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = database_url()
    if url.startswith("sqlite"):
        # worker thread runner + request API menulis bergantian → WAL + timeout tunggu lock
        engine = create_engine(url, pool_pre_ping=True, future=True, connect_args={"timeout": 30})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_con, _):
            cur = dbapi_con.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    else:
        engine = create_engine(url, pool_pre_ping=True, future=True)
    return engine


def backend_name() -> str:
    return "postgresql" if database_url().startswith("postgresql") else "sqlite"


if __name__ == "__main__":
    from sqlalchemy import text
    eng = get_engine()
    with eng.connect() as con:
        ver = con.execute(text("select version()" if backend_name() == "postgresql" else "select sqlite_version()")).scalar()
    print(f"OK {backend_name()}: {ver}")
