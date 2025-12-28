from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin

from crawler.html_table import parse_first_table
from db.dao import contest_exists, upsert_contests, upsert_problems
from oj.atcoder import atcoder_oj


def _parse_point(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_tasks(html: str, contest_id: str) -> list[dict]:
    rows = parse_first_table(html)
    problems = []
    contest_uid = atcoder_oj.contest_uid(contest_id)
    for row in rows:
        if len(row) < 2:
            continue
        index_text = row[0].get("text", "").strip()
        links = row[1].get("links", [])
        if not links:
            continue
        url = links[0]
        problem_id = url.strip("/").split("/")[-1]
        title_text = row[1].get("text", "").strip()
        task_index = index_text
        normalized = index_text.upper()
        if not normalized and title_text:
            token = title_text.split()[0].strip()
            normalized = token.upper()
            task_index = token
        if normalized == "EX" and contest_id.startswith("abc") and problem_id.endswith("_h"):
            task_index = "H"
        elif normalized in {"A", "B", "C", "D", "E", "F", "G", "H"}:
            task_index = normalized
        point = None
        if len(row) >= 3:
            point = _parse_point(row[2].get("text", ""))
        problems.append(
            {
                "problem_uid": atcoder_oj.problem_uid(
                    contest_id=contest_id,
                    index=task_index,
                    name=title_text,
                    problem_id=problem_id,
                ),
                "oj": atcoder_oj.name,
                "contest_uid": contest_uid,
                "contest_id": contest_id,
                "task_index": task_index,
                "title": row[1].get("text"),
                "point": point,
                "url": urljoin("https://atcoder.jp", url),
                "difficulty": None,
                "solved_count": None,
                "tags_json": None,
                "updated_epoch": None,
            }
        )
    return problems


def _contest_category(contest_id: str) -> str | None:
    prefix = []
    for ch in contest_id:
        if ch.isdigit():
            break
        prefix.append(ch)
    return "".join(prefix) or None


def crawl_tasks(fetch_html: Callable[[str], str], conn, contest_id: str) -> int:
    contest_uid = atcoder_oj.contest_uid(contest_id)
    if not contest_exists(conn, contest_uid):
        upsert_contests(
            conn,
            [
                {
                    "contest_uid": contest_uid,
                    "oj": atcoder_oj.name,
                    "contest_id": contest_id,
                    "title": contest_id,
                    "start_epoch": None,
                    "duration_sec": None,
                    "rated_range": None,
                    "category": _contest_category(contest_id),
                }
            ],
        )
    url = f"https://atcoder.jp/contests/{contest_id}/tasks"
    html = fetch_html(url)
    problems = parse_tasks(html, contest_id=contest_id)
    return upsert_problems(conn, problems)
