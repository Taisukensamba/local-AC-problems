from __future__ import annotations

import sqlite3
from typing import Iterable


def upsert_contests(conn: sqlite3.Connection, contests: Iterable[dict]) -> int:
    sql = (
        "INSERT INTO contests (contest_id, title, start_epoch, duration_sec, rated_range, category) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(contest_id) DO UPDATE SET "
        "title=excluded.title, "
        "start_epoch=excluded.start_epoch, "
        "duration_sec=excluded.duration_sec, "
        "rated_range=excluded.rated_range, "
        "category=excluded.category"
    )
    rows = [
        (
            c["contest_id"],
            c.get("title"),
            c.get("start_epoch"),
            c.get("duration_sec"),
            c.get("rated_range"),
            c.get("category"),
        )
        for c in contests
    ]
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def upsert_problems(conn: sqlite3.Connection, problems: Iterable[dict]) -> int:
    sql = (
        "INSERT INTO problems (problem_id, contest_id, task_index, title, point, url, difficulty, updated_epoch) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(problem_id) DO UPDATE SET "
        "contest_id=excluded.contest_id, "
        "task_index=excluded.task_index, "
        "title=excluded.title, "
        "point=excluded.point, "
        "url=excluded.url, "
        "difficulty=excluded.difficulty, "
        "updated_epoch=excluded.updated_epoch"
    )
    rows = [
        (
            p["problem_id"],
            p["contest_id"],
            p["task_index"],
            p["title"],
            p.get("point"),
            p["url"],
            p.get("difficulty"),
            p.get("updated_epoch"),
        )
        for p in problems
    ]
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def upsert_submissions(conn: sqlite3.Connection, submissions: Iterable[dict]) -> int:
    sql = (
        "INSERT INTO submissions (submission_id, problem_id, user_id, epoch_second, result, language, exec_ms, memory_kib, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(submission_id) DO UPDATE SET "
        "problem_id=excluded.problem_id, "
        "user_id=excluded.user_id, "
        "epoch_second=excluded.epoch_second, "
        "result=excluded.result, "
        "language=excluded.language, "
        "exec_ms=excluded.exec_ms, "
        "memory_kib=excluded.memory_kib, "
        "url=excluded.url"
    )
    rows = [
        (
            s["submission_id"],
            s["problem_id"],
            s["user_id"],
            s["epoch_second"],
            s["result"],
            s["language"],
            s.get("exec_ms"),
            s.get("memory_kib"),
            s["url"],
        )
        for s in submissions
    ]
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def upsert_submissions_with_stats(
    conn: sqlite3.Connection, submissions: list[dict]
) -> dict:
    if not submissions:
        return {"inserted": 0, "updated": 0}
    ids = [s["submission_id"] for s in submissions]
    existing = set()
    chunk_size = 900
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        rows = conn.execute(
            f"SELECT submission_id FROM submissions WHERE submission_id IN ({placeholders})",
            chunk,
        ).fetchall()
        existing.update(row[0] for row in rows)
    inserted = len([i for i in ids if i not in existing])
    updated = len(ids) - inserted
    upsert_submissions(conn, submissions)
    return {"inserted": inserted, "updated": updated}


def get_latest_submission_epoch(conn: sqlite3.Connection, user_id: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(epoch_second) FROM submissions WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return row[0]


def get_latest_submission_id(conn: sqlite3.Connection, user_id: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(submission_id) FROM submissions WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return row[0]


def update_problem_difficulties(
    conn: sqlite3.Connection, entries: Iterable[dict]
) -> int:
    sql = "UPDATE problems SET difficulty = ?, updated_epoch = ? WHERE problem_id = ?"
    rows = [
        (e.get("difficulty"), e.get("updated_epoch"), e["problem_id"]) for e in entries
    ]
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def get_sync_state(conn: sqlite3.Connection, user_id: str, contest_id: str) -> dict | None:
    row = conn.execute(
        "SELECT last_submission_id, last_epoch FROM sync_state WHERE user_id = ? AND contest_id = ?",
        (user_id, contest_id),
    ).fetchone()
    if row is None:
        return None
    return {"last_submission_id": row[0], "last_epoch": row[1]}


def upsert_sync_state(
    conn: sqlite3.Connection,
    user_id: str,
    contest_id: str,
    last_submission_id: int | None,
    last_epoch: int | None,
) -> None:
    conn.execute(
        "INSERT INTO sync_state (user_id, contest_id, last_submission_id, last_epoch) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, contest_id) DO UPDATE SET "
        "last_submission_id=excluded.last_submission_id, "
        "last_epoch=excluded.last_epoch",
        (user_id, contest_id, last_submission_id, last_epoch),
    )


def ensure_sync_state(conn: sqlite3.Connection, user_id: str, contest_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sync_state (user_id, contest_id) VALUES (?, ?)",
        (user_id, contest_id),
    )


def list_problem_ids_by_contest(
    conn: sqlite3.Connection, contest_id: str
) -> set[str]:
    rows = conn.execute(
        "SELECT problem_id FROM problems WHERE contest_id = ?", (contest_id,)
    ).fetchall()
    return {row[0] for row in rows}
