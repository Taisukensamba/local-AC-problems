from __future__ import annotations

import json
from typing import Callable
from urllib.parse import quote_plus

from db.dao import replace_problem_tags, upsert_contests, upsert_problems, upsert_submissions_with_stats, upsert_sync_state
from oj.codeforces import codeforces_oj


def _parse_api_payload(payload: str) -> dict:
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get("status") != "OK":
        raise ValueError("codeforces api: invalid response")
    return data


def parse_problemset(payload: str) -> tuple[list[dict], dict[tuple[str, str], int]]:
    data = _parse_api_payload(payload)
    result = data.get("result", {})
    problems = result.get("problems", [])
    stats = result.get("problemStatistics", [])
    stats_map: dict[tuple[str, str], int] = {}
    for item in stats:
        contest_id = item.get("contestId")
        index = item.get("index")
        if contest_id is None or index is None:
            continue
        stats_map[(str(contest_id), str(index))] = int(item.get("solvedCount", 0))
    return problems, stats_map


def _build_problem_url(problem: dict) -> str:
    contest_id = problem.get("contestId")
    index = problem.get("index")
    name = problem.get("name", "")
    if contest_id and index:
        return f"https://codeforces.com/contest/{contest_id}/problem/{index}"
    if name:
        return f"https://codeforces.com/problemset?search={quote_plus(name)}"
    return "https://codeforces.com/problemset"


def normalize_problemset(
    problems: list[dict], stats_map: dict[tuple[str, str], int]
) -> tuple[list[dict], dict[str, list[str]], list[dict]]:
    normalized: list[dict] = []
    tags_by_uid: dict[str, list[str]] = {}
    contests: dict[str, dict] = {}
    for problem in problems:
        contest_id_raw = problem.get("contestId")
        contest_id = str(contest_id_raw) if contest_id_raw is not None else None
        index = problem.get("index")
        name = problem.get("name") or ""
        tags = problem.get("tags") or []
        problemset_name = problem.get("problemsetName")
        problem_uid = codeforces_oj.problem_uid(
            contest_id=contest_id,
            index=index,
            name=name,
            problemset_name=problemset_name,
        )
        contest_uid = codeforces_oj.contest_uid(contest_id) if contest_id else None
        if contest_id:
            contests.setdefault(
                contest_uid,
                {
                    "contest_uid": contest_uid,
                    "oj": codeforces_oj.name,
                    "contest_id": contest_id,
                    "title": f"Codeforces {contest_id}",
                    "start_epoch": None,
                    "duration_sec": None,
                    "rated_range": None,
                    "category": "codeforces",
                },
            )
        solved_count = None
        if contest_id and index:
            solved_count = stats_map.get((contest_id, str(index)))
        normalized.append(
            {
                "problem_uid": problem_uid,
                "oj": codeforces_oj.name,
                "contest_uid": contest_uid,
                "contest_id": contest_id,
                "task_index": index,
                "title": name,
                "point": problem.get("points"),
                "url": _build_problem_url(problem),
                "difficulty": problem.get("rating"),
                "solved_count": solved_count,
                "tags_json": json.dumps(tags),
                "updated_epoch": None,
            }
        )
        tags_by_uid[problem_uid] = [str(tag) for tag in tags]
    return normalized, tags_by_uid, list(contests.values())


def sync_problemset(
    fetch_json: Callable[[str], str], conn
) -> dict:
    url = "https://codeforces.com/api/problemset.problems"
    payload = fetch_json(url)
    problems, stats_map = parse_problemset(payload)
    normalized, tags_by_uid, contests = normalize_problemset(problems, stats_map)
    upsert_contests(conn, contests)
    upserted = upsert_problems(conn, normalized)
    for problem_uid, tags in tags_by_uid.items():
        replace_problem_tags(conn, problem_uid, tags)
    return {"problems": upserted, "tags": len(tags_by_uid)}


def parse_user_status(payload: str, handle: str) -> list[dict]:
    data = _parse_api_payload(payload)
    submissions: list[dict] = []
    for item in data.get("result", []):
        problem = item.get("problem", {})
        contest_id_raw = problem.get("contestId")
        contest_id = str(contest_id_raw) if contest_id_raw is not None else None
        index = problem.get("index")
        name = problem.get("name") or ""
        rating = problem.get("rating")
        points = problem.get("points")
        tags = problem.get("tags") or []
        problemset_name = problem.get("problemsetName")
        problem_uid = codeforces_oj.problem_uid(
            contest_id=contest_id,
            index=index,
            name=name,
            problemset_name=problemset_name,
        )
        verdict = item.get("verdict") or "UNKNOWN"
        submission_id = item.get("id")
        submission_uid = codeforces_oj.submission_uid(submission_id)
        if contest_id:
            url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
        else:
            url = f"https://codeforces.com/submissions/{handle}"
        memory_bytes = item.get("memoryConsumedBytes")
        memory_kib = int(memory_bytes / 1024) if isinstance(memory_bytes, int) else None
        submissions.append(
            {
                "submission_id": submission_id,
                "submission_uid": submission_uid,
                "oj": codeforces_oj.name,
                "problem_uid": problem_uid,
                "problem_contest_id": contest_id,
                "problem_index": index,
                "problem_name": name,
                "problem_rating": rating,
                "problem_points": points,
                "problem_tags": tags,
                "problem_problemset_name": problemset_name,
                "user_id": handle,
                "epoch_second": item.get("creationTimeSeconds") or 0,
                "result": verdict,
                "language": item.get("programmingLanguage") or "",
                "exec_ms": item.get("timeConsumedMillis"),
                "memory_kib": memory_kib,
                "url": url,
            }
        )
    return submissions


def sync_user_status(
    fetch_json: Callable[[str], str],
    conn,
    handle: str,
    last_seen_id: int | None,
    page_size: int = 200,
) -> dict:
    inserted = 0
    updated = 0
    newest_id = last_seen_id
    offset = 1
    while True:
        url = (
            f"https://codeforces.com/api/user.status?handle={handle}"
            f"&from={offset}&count={page_size}"
        )
        payload = fetch_json(url)
        submissions = parse_user_status(payload, handle)
        if not submissions:
            break
        if last_seen_id is not None:
            submissions = [
                s for s in submissions if s["submission_id"] and s["submission_id"] > last_seen_id
            ]
        if not submissions:
            break
        problems = {}
        contests = {}
        for s in submissions:
            contest_id = s.get("problem_contest_id")
            contest_uid = codeforces_oj.contest_uid(contest_id) if contest_id else None
            if contest_id:
                contests.setdefault(
                    contest_uid,
                    {
                        "contest_uid": contest_uid,
                        "oj": codeforces_oj.name,
                        "contest_id": contest_id,
                        "title": f"Codeforces {contest_id}",
                        "start_epoch": None,
                        "duration_sec": None,
                        "rated_range": None,
                        "category": "codeforces",
                    },
                )
            problem_uid = s["problem_uid"]
            if problem_uid not in problems:
                problems[problem_uid] = {
                    "problem_uid": problem_uid,
                    "oj": codeforces_oj.name,
                    "contest_uid": contest_uid,
                    "contest_id": contest_id,
                    "task_index": s.get("problem_index"),
                    "title": s.get("problem_name") or problem_uid,
                    "point": s.get("problem_points"),
                    "url": _build_problem_url(
                        {
                            "contestId": contest_id,
                            "index": s.get("problem_index"),
                            "name": s.get("problem_name"),
                        }
                    ),
                    "difficulty": s.get("problem_rating"),
                    "solved_count": None,
                    "tags_json": json.dumps(s.get("problem_tags") or []),
                    "updated_epoch": None,
                }
        if contests:
            upsert_contests(conn, contests.values())
        if problems:
            upsert_problems(conn, problems.values())
            for s in submissions:
                replace_problem_tags(conn, s["problem_uid"], s.get("problem_tags") or [])
        stats = upsert_submissions_with_stats(conn, submissions)
        inserted += stats["inserted"]
        updated += stats["updated"]
        newest_id = max(newest_id or 0, max(s["submission_id"] or 0 for s in submissions))
        offset += page_size
    if newest_id is not None:
        upsert_sync_state(conn, handle, codeforces_oj.name, "global", str(newest_id), None)
    return {"inserted": inserted, "updated": updated, "last_seen_id": newest_id}


def parse_contest_list(payload: str) -> list[dict]:
    data = _parse_api_payload(payload)
    contests = []
    for item in data.get("result", []):
        contest_id = str(item.get("id"))
        name = item.get("name") or f"Codeforces {contest_id}"
        category = _classify_contest_name(name)
        contests.append(
            {
                "contest_uid": codeforces_oj.contest_uid(contest_id),
                "oj": codeforces_oj.name,
                "contest_id": contest_id,
                "title": name,
                "start_epoch": item.get("startTimeSeconds"),
                "duration_sec": item.get("durationSeconds"),
                "rated_range": None,
                "category": category,
            }
        )
    return contests


def _classify_contest_name(name: str) -> str:
    if "Educational Codeforces Round" in name:
        return "cf-ecr"
    if "Codeforces Global Round" in name:
        return "cf-global"
    if "Div. 1 + Div. 2" in name or "Div. 1+2" in name:
        return "cf-div1+2"
    if "Div. 1" in name:
        return "cf-div1"
    if "Div. 2" in name:
        return "cf-div2"
    if "Div. 3" in name:
        return "cf-div3"
    if "Div. 4" in name:
        return "cf-div4"
    return "codeforces"


def sync_contests(
    fetch_json: Callable[[str], str], conn, include_gym: bool
) -> int:
    gym = "true" if include_gym else "false"
    url = f"https://codeforces.com/api/contest.list?gym={gym}"
    payload = fetch_json(url)
    contests = parse_contest_list(payload)
    return upsert_contests(conn, contests)
