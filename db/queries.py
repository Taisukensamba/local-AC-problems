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
    exclude_ahc: bool,
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
        conditions.append("(p.title LIKE ? OR p.problem_id LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if contest:
        conditions.append("p.contest_id = ?")
        params.append(contest)
    if exclude_ahc:
        conditions.append("p.contest_id NOT GLOB 'ahc[0-9]*'")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = (
        "SELECT "
        "p.problem_id, p.contest_id, p.task_index, p.title, p.point, p.url, p.difficulty, "
        "COALESCE(pr.is_ac, 0) AS is_ac, "
        "pr.first_ac_epoch, pr.last_submit_epoch, pr.ac_count, pr.wa_count "
        "FROM problems p "
        "LEFT JOIN progress pr ON pr.problem_id = p.problem_id AND pr.user_id = ? "
        f"{where} "
        "ORDER BY p.contest_id, p.task_index "
        "LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    results = []
    for row in rows:
        results.append(
            {
                "problem_id": row[0],
                "contest_id": row[1],
                "task_index": row[2],
                "title": row[3],
                "point": row[4],
                "url": row[5],
                "difficulty": row[6],
                "is_ac": bool(row[7]),
                "first_ac_epoch": row[8],
                "last_submit_epoch": row[9],
                "ac_count": row[10] or 0,
                "wa_count": row[11] or 0,
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
        "LEFT JOIN progress pr ON pr.problem_id = p.problem_id AND pr.user_id = ? "
        "WHERE p.contest_id NOT GLOB 'ahc[0-9]*' "
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
        "SELECT s.submission_id, s.problem_id, s.epoch_second, s.result, s.language, s.url, "
        "p.title, p.contest_id "
        "FROM submissions s "
        "LEFT JOIN problems p ON p.problem_id = s.problem_id "
        "WHERE s.user_id = ? AND (p.contest_id IS NULL OR p.contest_id NOT GLOB 'ahc[0-9]*') "
        "ORDER BY s.epoch_second DESC "
        "LIMIT ?"
    )
    rows = conn.execute(sql, (user_id, limit)).fetchall()
    results = []
    for row in rows:
        results.append(
            {
                "submission_id": row[0],
                "problem_id": row[1],
                "epoch_second": row[2],
                "result": row[3],
                "language": row[4],
                "url": row[5],
                "title": row[6],
                "contest_id": row[7],
            }
        )
    return results


def list_contest_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT contest_id FROM contests ORDER BY contest_id").fetchall()
    return [row[0] for row in rows]


def list_contests_by_prefix(
    conn: sqlite3.Connection, prefix: str, limit: int, offset: int
) -> list[str]:
    glob = f"{prefix}[0-9]*"
    start = len(prefix) + 1
    rows = conn.execute(
        "SELECT contest_id FROM contests "
        "WHERE contest_id GLOB ? "
        "ORDER BY CAST(SUBSTR(contest_id, ?) AS INTEGER) DESC "
        "LIMIT ? OFFSET ?",
        (glob, start, limit, offset),
    ).fetchall()
    return [row[0] for row in rows]


def list_contests_other(conn: sqlite3.Connection, limit: int, offset: int) -> list[str]:
    rows = conn.execute(
        "SELECT contest_id FROM contests "
        "WHERE contest_id NOT GLOB 'abc[0-9]*' "
        "AND contest_id NOT GLOB 'arc[0-9]*' "
        "AND contest_id NOT GLOB 'agc[0-9]*' "
        "AND contest_id NOT GLOB 'ahc[0-9]*' "
        "ORDER BY start_epoch DESC, contest_id DESC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [row[0] for row in rows]


def problems_by_contest(
    conn: sqlite3.Connection, user_id: str, contest_ids: list[str]
) -> dict[str, list[dict]]:
    if not contest_ids:
        return {}
    placeholders = ",".join(["?"] * len(contest_ids))
    sql = (
        "SELECT p.contest_id, p.task_index, p.title, p.url, p.difficulty, COALESCE(pr.is_ac, 0), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "JOIN contests c ON c.contest_id = p.contest_id "
        "WHERE s.problem_id = p.problem_id AND s.user_id = ? "
        "AND s.result = 'AC' "
        "AND c.start_epoch IS NOT NULL AND c.duration_sec IS NOT NULL "
        "AND s.epoch_second BETWEEN c.start_epoch AND c.start_epoch + c.duration_sec"
        "), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "JOIN contests c ON c.contest_id = p.contest_id "
        "WHERE s.problem_id = p.problem_id AND s.user_id = ? "
        "AND c.start_epoch IS NOT NULL AND c.duration_sec IS NOT NULL "
        "AND s.epoch_second BETWEEN c.start_epoch AND c.start_epoch + c.duration_sec"
        "), "
        "EXISTS ("
        "SELECT 1 FROM submissions s "
        "WHERE s.problem_id = p.problem_id AND s.user_id = ? "
        "AND s.result != 'AC'"
        ") "
        "FROM problems p "
        "LEFT JOIN progress pr ON pr.problem_id = p.problem_id AND pr.user_id = ? "
        f"WHERE p.contest_id IN ({placeholders}) "
        "ORDER BY p.contest_id, p.task_index"
    )
    rows = conn.execute(sql, [user_id, user_id, user_id, user_id, *contest_ids]).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(
            {
                "task_index": row[1],
                "title": row[2],
                "url": row[3],
                "difficulty": row[4],
                "is_ac": bool(row[5]),
                "contest_ac": bool(row[6]),
                "contest_submitted": bool(row[7]),
                "non_contest_wa": bool(row[8]),
            }
        )
    return grouped


def list_contests_missing_tasks(conn: sqlite3.Connection, contest_ids: list[str]) -> list[str]:
    if not contest_ids:
        return []
    placeholders = ",".join(["?"] * len(contest_ids))
    rows = conn.execute(
        "SELECT c.contest_id FROM contests c "
        "LEFT JOIN problems p ON p.contest_id = c.contest_id "
        f"WHERE c.contest_id IN ({placeholders}) "
        "GROUP BY c.contest_id "
        "HAVING COUNT(p.problem_id) = 0",
        contest_ids,
    ).fetchall()
    return [row[0] for row in rows]


def list_contests_missing_submissions(
    conn: sqlite3.Connection, user_id: str, contest_ids: list[str]
) -> list[str]:
    if not contest_ids:
        return []
    placeholders = ",".join(["?"] * len(contest_ids))
    rows = conn.execute(
        "SELECT c.contest_id FROM contests c "
        "LEFT JOIN sync_state ss ON ss.user_id = ? AND ss.contest_id = c.contest_id "
        "LEFT JOIN problems p ON p.contest_id = c.contest_id "
        "LEFT JOIN submissions s ON s.problem_id = p.problem_id AND s.user_id = ? "
        f"WHERE c.contest_id IN ({placeholders}) "
        "GROUP BY c.contest_id "
        "HAVING COUNT(s.submission_id) = 0 AND MAX(ss.user_id) IS NULL",
        [user_id, user_id, *contest_ids],
    ).fetchall()
    return [row[0] for row in rows]
