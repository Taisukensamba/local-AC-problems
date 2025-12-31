from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path


def get_db_path() -> str:
    return os.getenv("AC_DB_PATH", "data/atcoder.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
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


def _read_migration_file(filename: str) -> str:
    migrations_dir = Path(__file__).resolve().parent.parent / "data" / "migrations"
    return (migrations_dir / filename).read_text(encoding="utf-8")


def init_db(db_path: str | None = None) -> None:
    path = Path(db_path or get_db_path())
    existed = path.exists()
    non_empty = existed and path.stat().st_size > 0
    conn = connect(str(path))
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        current_version = row[0] if row else 0
        if current_version >= 6:
            return
        if current_version < 4:
            if non_empty:
                allow_rebuild = os.getenv("AC_DB_ALLOW_REBUILD", "false").lower() == "true"
                if not allow_rebuild:
                    raise RuntimeError(
                        "db schema is outdated; set AC_DB_ALLOW_REBUILD=true to rebuild (will drop data)"
                    )
                backup_path = path.with_suffix(f"{path.suffix}.bak-{int(time.time())}")
                shutil.copy2(path, backup_path)
            sql = _read_migration_sql(version=4)
            conn.executescript(sql)
            conn.commit()
            current_version = 4
        if current_version in (4, 5):
            sql = _read_migration_file("005_progress_view_not_ac.sql")
            conn.executescript(sql)
            conn.commit()
            current_version = 6
    finally:
        conn.close()
