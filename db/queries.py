from __future__ import annotations

import sqlite3


def search_problems(
    conn: sqlite3.Connection,
    user_id: str,
    status: str | None,
    min_diff: int | None,
    max_diff: int | None,
    query: str | None,
    contest: str | None,
    oj: str | None,
    tag: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    conditions = []
    params: list[object] = [user_id]

    if status == "solved":
        conditions.append("COALESCE(pr.is_ac, 0) = 1")
    elif status == "unsolved":
        conditions.append("COALESCE(pr.is_ac, 0) = 0")

    if min_diff is not None:
        conditions.append("p.difficulty >= ?")
        params.append(min_diff)
    if max_diff is not None:
        conditions.append("p.difficulty <= ?")
        params.append(max_diff)
    if query:
        conditions.append("(p.title LIKE ? OR p.problem_uid LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if contest:
        conditions.append("p.contest_id = ?")
        params.append(contest)
    if oj and oj != "all":
        conditions.append("p.oj = ?")
        params.append(oj)
    if tag:
        conditions.append(
            "EXISTS (SELECT 1 FROM problem_tags pt WHERE pt.problem_uid = p.problem_uid AND pt.tag = ?)"
        )
        params.append(tag)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = (
        "SELECT "
        "p.problem_uid, p.oj, p.contest_id, p.task_index, p.title, p.point, p.url, p.difficulty, "
        "COALESCE(pr.is_ac, 0) AS is_ac, "
        "pr.first_ac_epoch, pr.last_submit_epoch, pr.ac_count, pr.wa_count, "
        "GROUP_CONCAT(pt.tag) "
        "FROM problems p "
        "LEFT JOIN progress pr ON pr.problem_uid = p.problem_uid AND pr.user_id = ? "
        "LEFT JOIN problem_tags pt ON pt.problem_uid = p.problem_uid "
        f"{where} "
        "GROUP BY p.problem_uid, pr.user_id "
        "ORDER BY p.oj, p.contest_id, p.task_index "
        "LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    results = []
    for row in rows:
        tags = row[13].split(",") if row[13] else []
        results.append(
            {
                "problem_uid": row[0],
                "oj": row[1],
                "contest_id": row[2],
                "task_index": row[3],
                "title": row[4],
                "point": row[5],
                "url": row[6],
                "difficulty": row[7],
                "is_ac": bool(row[8]),
                "first_ac_epoch": row[9],
                "last_submit_epoch": row[10],
                "ac_count": row[11] or 0,
                "wa_count": row[12] or 0,
                "tags": tags,
            }
        )
    return results


def progress_summary(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    bins = [
        ("unknown", None),
        ("<0", -1),
        ("0-399", 0),
        ("400-799", 400),
        ("800-1199", 800),
        ("1200-1599", 1200),
        ("1600-1999", 1600),
        ("2000-2399", 2000),
        ("2400-2799", 2400),
        ("2800-3199", 2800),
        ("3200-3599", 3200),
        ("3600-3999", 3600),
        ("4000+", 4000),
    ]
    sql = (
        "SELECT "
        "CASE "
        "WHEN p.difficulty IS NULL THEN 'unknown' "
        "WHEN p.difficulty < 0 THEN '<0' "
        "WHEN p.difficulty BETWEEN 0 AND 399 THEN '0-399' "
        "WHEN p.difficulty BETWEEN 400 AND 799 THEN '400-799' "
        "WHEN p.difficulty BETWEEN 800 AND 1199 THEN '800-1199' "
        "WHEN p.difficulty BETWEEN 1200 AND 1599 THEN '1200-1599' "
        "WHEN p.difficulty BETWEEN 1600 AND 1999 THEN '1600-1999' "
        "WHEN p.difficulty BETWEEN 2000 AND 2399 THEN '2000-2399' "
        "WHEN p.difficulty BETWEEN 2400 AND 2799 THEN '2400-2799' "
        "WHEN p.difficulty BETWEEN 2800 AND 3199 THEN '2800-3199' "
        "WHEN p.difficulty BETWEEN 3200 AND 3599 THEN '3200-3599' "
        "WHEN p.difficulty BETWEEN 3600 AND 3999 THEN '3600-3999' "
        "ELSE '4000+' END AS bin, "
        "SUM(CASE WHEN COALESCE(pr.is_ac, 0) = 1 THEN 1 ELSE 0 END) AS ac_count, "
        "COUNT(*) AS total_count "
        "FROM problems p "
        "LEFT JOIN progress pr ON pr.problem_uid = p.problem_uid AND pr.user_id = ? "
        "GROUP BY bin"
    )
    rows = conn.execute(sql, (user_id,)).fetchall()
    by_bin = {row[0]: {"ac_count": row[1] or 0, "total_count": row[2] or 0} for row in rows}
    summary = []
    for label, _ in bins:
        data = by_bin.get(label, {"ac_count": 0, "total_count": 0})
        summary.append(
            {"bin": label, "ac_count": data["ac_count"], "total_count": data["total_count"]}
        )
    return summary


def recent_submissions(conn: sqlite3.Connection, user_id: str, limit: int) -> list[dict]:
    sql = (
        "SELECT s.submission_uid, s.problem_uid, s.epoch_second, s.result, s.language, s.url, "
        "p.title, p.contest_id, p.oj "
        "FROM submissions s "
        "LEFT JOIN problems p ON p.problem_uid = s.problem_uid "
        "WHERE s.user_id = ? "
        "ORDER BY s.epoch_second DESC "
        "LIMIT ?"
    )
    rows = conn.execute(sql, (user_id, limit)).fetchall()
    results = []
    for row in rows:
        results.append(
            {
                "submission_uid": row[0],
                "problem_uid": row[1],
                "epoch_second": row[2],
                "result": row[3],
                "language": row[4],
                "url": row[5],
                "title": row[6],
                "contest_id": row[7],
                "oj": row[8],
            }
        )
    return results


def list_contest_uids(conn: sqlite3.Connection, oj: str | None = None) -> list[str]:
    if oj:
        rows = conn.execute(
            "SELECT contest_uid FROM contests WHERE oj = ? ORDER BY contest_id", (oj,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT contest_uid FROM contests ORDER BY contest_id").fetchall()
    return [row[0] for row in rows]


def list_contest_uids_by_prefix(
    conn: sqlite3.Connection, prefix: str, limit: int, offset: int
) -> list[str]:
    glob = f"{prefix}[0-9]*"
    start = len(prefix) + 1
    rows = conn.execute(
        "SELECT contest_uid FROM contests "
        "WHERE oj = 'atcoder' AND contest_id GLOB ? "
        "ORDER BY CAST(SUBSTR(contest_id, ?) AS INTEGER) DESC "
        "LIMIT ? OFFSET ?",
        (glob, start, limit, offset),
    ).fetchall()
    return [row[0] for row in rows]


def list_contest_uids_by_category(
    conn: sqlite3.Connection, oj: str, category: str, limit: int, offset: int
) -> list[str]:
    rows = conn.execute(
        "SELECT contest_uid FROM contests "
        "WHERE oj = ? AND category = ? "
        "ORDER BY start_epoch DESC, contest_id DESC "
        "LIMIT ? OFFSET ?",
        (oj, category, limit, offset),
    ).fetchall()
    return [row[0] for row in rows]


def get_contest_titles(conn: sqlite3.Connection, contest_uids: list[str]) -> dict[str, str]:
    if not contest_uids:
        return {}
    placeholders = ",".join(["?"] * len(contest_uids))
    rows = conn.execute(
        f"SELECT contest_uid, title FROM contests WHERE contest_uid IN ({placeholders})",
        contest_uids,
    ).fetchall()
    return {row[0]: row[1] for row in rows}

def problems_by_contest(
    conn: sqlite3.Connection, user_id: str, contest_uids: list[str]
) -> dict[str, list[dict]]:
    if not contest_uids:
        return {}
    placeholders = ",".join(["?"] * len(contest_uids))
    sql = (
        "SELECT p.contest_uid, p.contest_id, p.task_index, p.title, p.url, p.difficulty, "
        "COALESCE(pr.is_ac, 0), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "JOIN contests c ON c.contest_uid = p.contest_uid "
        "WHERE s.problem_uid = p.problem_uid AND s.user_id = ? "
        "AND s.result IN ('AC', 'OK') "
        "AND c.start_epoch IS NOT NULL AND c.duration_sec IS NOT NULL "
        "AND s.epoch_second BETWEEN c.start_epoch AND c.start_epoch + c.duration_sec"
        "), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "JOIN contests c ON c.contest_uid = p.contest_uid "
        "WHERE s.problem_uid = p.problem_uid AND s.user_id = ? "
        "AND c.start_epoch IS NOT NULL AND c.duration_sec IS NOT NULL "
        "AND s.epoch_second BETWEEN c.start_epoch AND c.start_epoch + c.duration_sec"
        "), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "WHERE s.problem_uid = p.problem_uid AND s.user_id = ? "
        "AND s.result NOT IN ('AC', 'OK')"
        ") "
        "FROM problems p "
        "LEFT JOIN progress pr ON pr.problem_uid = p.problem_uid AND pr.user_id = ? "
        f"WHERE p.contest_uid IN ({placeholders}) "
        "ORDER BY p.contest_id, p.task_index"
    )
    rows = conn.execute(sql, [user_id, user_id, user_id, user_id, *contest_uids]).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(
            {
                "contest_id": row[1],
                "task_index": row[2],
                "title": row[3],
                "url": row[4],
                "difficulty": row[5],
                "is_ac": bool(row[6]),
                "contest_ac": bool(row[7]),
                "contest_submitted": bool(row[8]),
                "non_contest_wa": bool(row[9]),
            }
        )
    return grouped


def list_contests_missing_tasks(conn: sqlite3.Connection, contest_uids: list[str]) -> list[str]:
    if not contest_uids:
        return []
    placeholders = ",".join(["?"] * len(contest_uids))
    rows = conn.execute(
        "SELECT c.contest_uid FROM contests c "
        "LEFT JOIN problems p ON p.contest_uid = c.contest_uid "
        f"WHERE c.contest_uid IN ({placeholders}) "
        "GROUP BY c.contest_uid "
        "HAVING COUNT(p.problem_uid) = 0",
        contest_uids,
    ).fetchall()
    return [row[0] for row in rows]


def list_contests_missing_submissions(
    conn: sqlite3.Connection, user_id: str, contest_uids: list[str]
) -> list[str]:
    if not contest_uids:
        return []
    placeholders = ",".join(["?"] * len(contest_uids))
    rows = conn.execute(
        "SELECT c.contest_uid FROM contests c "
        "LEFT JOIN sync_state ss ON ss.user_id = ? AND ss.oj = 'atcoder' AND ss.key = c.contest_uid "
        "LEFT JOIN problems p ON p.contest_uid = c.contest_uid "
        "LEFT JOIN submissions s ON s.problem_uid = p.problem_uid AND s.user_id = ? "
        f"WHERE c.contest_uid IN ({placeholders}) "
        "GROUP BY c.contest_uid "
        "HAVING COUNT(s.submission_uid) = 0 AND MAX(ss.user_id) IS NULL",
        [user_id, user_id, *contest_uids],
    ).fetchall()
    return [row[0] for row in rows]
