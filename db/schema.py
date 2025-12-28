from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_db_path() -> str:
    return os.getenv("AC_DB_PATH", "data/atcoder.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _read_migration_sql() -> str:
    migrations_dir = Path(__file__).resolve().parent.parent / "data" / "migrations"
    parts = []
    for path in sorted(migrations_dir.glob("*.sql")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def init_db(db_path: str | None = None) -> None:
    sql = _read_migration_sql()
    conn = connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
