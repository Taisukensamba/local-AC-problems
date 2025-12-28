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


def _read_migration_sql(version: int | None = None) -> str:
    migrations_dir = Path(__file__).resolve().parent.parent / "data" / "migrations"
    if version is not None:
        target = migrations_dir / f"{version:03d}_rebuild_oj.sql"
        if target.exists():
            return target.read_text(encoding="utf-8")
    parts = []
    for path in sorted(migrations_dir.glob("*.sql")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def init_db(db_path: str | None = None) -> None:
    conn = connect(db_path)
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        current_version = row[0] if row else 0
        if current_version >= 4:
            return
        sql = _read_migration_sql(version=4)
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
