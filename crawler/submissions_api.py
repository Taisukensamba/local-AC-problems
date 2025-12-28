from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlencode

from db.dao import get_latest_submission_epoch, upsert_submissions_with_stats

SAFETY_MARGIN = 300


def build_api_url(user_id: str, from_second: int) -> str:
    params = urlencode({"user": user_id, "from_second": from_second})
    return f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?{params}"


def parse_submissions(payload: str) -> list[dict]:
    data = json.loads(payload)
    submissions = []
    for item in data:
        submissions.append(
            {
                "submission_id": item["id"],
                "problem_id": item["problem_id"],
                "user_id": item["user_id"],
                "contest_id": item["contest_id"],
                "epoch_second": item["epoch_second"],
                "result": item["result"],
                "language": item["language"],
                "exec_ms": item.get("execution_time"),
                "memory_kib": item.get("memory"),
                "url": f"https://atcoder.jp/contests/{item['contest_id']}/submissions/{item['id']}",
            }
        )
    return submissions


def list_updated_contests(
    fetch_json: Callable[[str], str],
    conn,
    user_id: str,
) -> list[str]:
    last_epoch = get_latest_submission_epoch(conn, user_id) or 0
    from_second = max(0, last_epoch - SAFETY_MARGIN)
    url = build_api_url(user_id, from_second)
    payload = fetch_json(url)
    data = json.loads(payload)
    contests = set()
    for item in data:
        if item.get("epoch_second", 0) <= last_epoch:
            continue
        contest_id = item.get("contest_id")
        if contest_id:
            contests.add(contest_id)
    return sorted(contests)


def sync_submissions_api(
    fetch_json: Callable[[str], str],
    conn,
    user_id: str,
) -> dict:
    last_epoch = get_latest_submission_epoch(conn, user_id) or 0
    from_second = max(0, last_epoch - SAFETY_MARGIN)
    url = build_api_url(user_id, from_second)
    payload = fetch_json(url)
    submissions = parse_submissions(payload)
    return upsert_submissions_with_stats(conn, submissions)
