from __future__ import annotations

import sqlite3
from typing import Iterable


def upsert_contests(conn: sqlite3.Connection, contests: Iterable[dict]) -> int:
    sql = (
        "INSERT INTO contests (contest_uid, oj, contest_id, title, start_epoch, duration_sec, rated_range, category) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(contest_uid) DO UPDATE SET "
        "oj=excluded.oj, "
        "contest_id=excluded.contest_id, "
        "title=CASE "
        "WHEN excluded.title = ('Codeforces ' || excluded.contest_id) "
        "AND contests.title IS NOT NULL "
        "AND contests.title != excluded.title "
        "THEN contests.title "
        "ELSE excluded.title END, "
        "start_epoch=COALESCE(excluded.start_epoch, contests.start_epoch), "
        "duration_sec=COALESCE(excluded.duration_sec, contests.duration_sec), "
        "rated_range=COALESCE(excluded.rated_range, contests.rated_range), "
        "category=CASE "
        "WHEN excluded.category IS NULL THEN contests.category "
        "WHEN excluded.category = 'codeforces' "
        "AND contests.category IS NOT NULL "
        "AND contests.category != 'codeforces' "
        "THEN contests.category "
        "ELSE excluded.category END"
    )
    rows = [
        (
            c["contest_uid"],
            c["oj"],
            c.get("contest_id"),
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
        "INSERT INTO problems "
        "(problem_uid, oj, contest_uid, contest_id, task_index, title, point, url, difficulty, solved_count, tags_json, updated_epoch) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(problem_uid) DO UPDATE SET "
        "oj=excluded.oj, "
        "contest_uid=excluded.contest_uid, "
        "contest_id=excluded.contest_id, "
        "task_index=excluded.task_index, "
        "title=excluded.title, "
        "point=excluded.point, "
        "url=excluded.url, "
        "difficulty=excluded.difficulty, "
        "solved_count=excluded.solved_count, "
        "tags_json=excluded.tags_json, "
        "updated_epoch=excluded.updated_epoch"
    )
    rows = [
        (
            p["problem_uid"],
            p["oj"],
            p.get("contest_uid"),
            p.get("contest_id"),
            p.get("task_index"),
            p["title"],
            p.get("point"),
            p["url"],
            p.get("difficulty"),
            p.get("solved_count"),
            p.get("tags_json"),
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
        "INSERT INTO submissions "
        "(submission_uid, oj, problem_uid, user_id, epoch_second, result, language, exec_ms, memory_kib, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(submission_uid) DO UPDATE SET "
        "oj=excluded.oj, "
        "problem_uid=excluded.problem_uid, "
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
            s["submission_uid"],
            s["oj"],
            s["problem_uid"],
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
    ids = [s["submission_uid"] for s in submissions]
    existing = set()
    chunk_size = 900
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        rows = conn.execute(
            f"SELECT submission_uid FROM submissions WHERE submission_uid IN ({placeholders})",
            chunk,
        ).fetchall()
        existing.update(row[0] for row in rows)
    inserted = len([i for i in ids if i not in existing])
    updated = len(ids) - inserted
    upsert_submissions(conn, submissions)
    return {"inserted": inserted, "updated": updated}

def get_latest_submission_epoch(
    conn: sqlite3.Connection, user_id: str, oj: str | None = None
) -> int | None:
    if oj:
        row = conn.execute(
            "SELECT MAX(epoch_second) FROM submissions WHERE user_id = ? AND oj = ?",
            (user_id, oj),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(epoch_second) FROM submissions WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return row[0]


def get_latest_submission_id(
    conn: sqlite3.Connection, user_id: str, oj: str | None = None
) -> str | None:
    if oj:
        row = conn.execute(
            "SELECT MAX(submission_uid) FROM submissions WHERE user_id = ? AND oj = ?",
            (user_id, oj),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(submission_uid) FROM submissions WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return row[0]


def update_problem_difficulties(
    conn: sqlite3.Connection, entries: Iterable[dict]
) -> int:
    sql = "UPDATE problems SET difficulty = ?, updated_epoch = ? WHERE problem_uid = ?"
    rows = [
        (e.get("difficulty"), e.get("updated_epoch"), e["problem_uid"]) for e in entries
    ]
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def get_sync_state(
    conn: sqlite3.Connection, user_id: str, oj: str, key: str
) -> dict | None:
    row = conn.execute(
        "SELECT last_submission_id, last_epoch "
        "FROM sync_state WHERE user_id = ? AND oj = ? AND key = ?",
        (user_id, oj, key),
    ).fetchone()
    if row is None:
        return None
    return {"last_submission_id": row[0], "last_epoch": row[1]}


def upsert_sync_state(
    conn: sqlite3.Connection,
    user_id: str,
    oj: str,
    key: str,
    last_submission_id: str | None,
    last_epoch: int | None,
) -> None:
    conn.execute(
        "INSERT INTO sync_state (user_id, oj, key, last_submission_id, last_epoch) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, oj, key) DO UPDATE SET "
        "last_submission_id=excluded.last_submission_id, "
        "last_epoch=excluded.last_epoch",
        (user_id, oj, key, last_submission_id, last_epoch),
    )


def ensure_sync_state(conn: sqlite3.Connection, user_id: str, oj: str, key: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sync_state (user_id, oj, key) VALUES (?, ?, ?)",
        (user_id, oj, key),
    )


def list_problem_uids_by_contest(
    conn: sqlite3.Connection, contest_uid: str
) -> set[str]:
    rows = conn.execute(
        "SELECT problem_uid FROM problems WHERE contest_uid = ?", (contest_uid,)
    ).fetchall()
    return {row[0] for row in rows}


def replace_problem_tags(conn: sqlite3.Connection, problem_uid: str, tags: Iterable[str]) -> None:
    conn.execute("DELETE FROM problem_tags WHERE problem_uid = ?", (problem_uid,))
    rows = [(problem_uid, tag) for tag in sorted(set(tags))]
    if rows:
        conn.executemany(
            "INSERT INTO problem_tags (problem_uid, tag) VALUES (?, ?)",
            rows,
        )


def contest_exists(conn: sqlite3.Connection, contest_uid: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM contests WHERE contest_uid = ? LIMIT 1", (contest_uid,)
    ).fetchone()
    return row is not None
