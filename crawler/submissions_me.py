from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin

from crawler.html_table import parse_first_table
from db.dao import (
    ensure_sync_state,
    get_sync_state,
    list_problem_uids_by_contest,
    upsert_submissions_with_stats,
    upsert_sync_state,
)
from oj.atcoder import atcoder_oj

JST = timezone(timedelta(hours=9))


def _parse_epoch(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def _parse_int_prefix(text: str) -> int | None:
    text = text.strip()
    digits = []
    for ch in text:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if not digits:
        return None
    return int("".join(digits))


def detect_login_required(html: str) -> bool:
    markers = ["Sign In", "name=\"username\"", "action=\"/login\"", "ログイン"]
    return any(marker in html for marker in markers)


def parse_submissions_me(html: str, contest_id: str, user_id: str) -> list[dict]:
    rows = parse_first_table(html)
    submissions = []
    for row in rows:
        if len(row) < 8:
            continue
        time_text = row[0].get("text", "")
        is_time_first = ("-" in time_text and ":" in time_text)
        if is_time_first:
            time_text = row[0].get("text", "")
            problem_links = row[1].get("links", [])
            language = row[3].get("text", "")
            result = row[6].get("text", "")
            exec_ms = _parse_int_prefix(row[7].get("text", "")) if len(row) >= 8 else None
            memory_kib = _parse_int_prefix(row[8].get("text", "")) if len(row) >= 9 else None
        else:
            time_text = row[1].get("text", "")
            problem_links = row[2].get("links", [])
            language = row[4].get("text", "")
            result = row[7].get("text", "")
            exec_ms = _parse_int_prefix(row[8].get("text", "")) if len(row) >= 9 else None
            memory_kib = _parse_int_prefix(row[9].get("text", "")) if len(row) >= 10 else None
        if not problem_links:
            continue
        problem_id = problem_links[0].strip("/").split("/")[-1]
        submission_id = None
        submission_href = None
        for cell in row:
            for link in cell.get("links", []):
                if "/submissions/" in link and "/submissions/me" not in link:
                    submission_href = link
                    submission_id_text = (
                        link.split("?", 1)[0].strip("/").split("/")[-1]
                    )
                    if submission_id_text.isdigit():
                        submission_id = int(submission_id_text)
                        break
            if submission_id is not None:
                break
        if submission_id is None or submission_href is None:
            continue
        submissions.append(
            {
                "submission_id": submission_id,
                "submission_uid": atcoder_oj.submission_uid(submission_id),
                "oj": atcoder_oj.name,
                "problem_uid": atcoder_oj.problem_uid(
                    contest_id=contest_id,
                    index=None,
                    name=None,
                    problem_id=problem_id,
                ),
                "user_id": user_id,
                "epoch_second": _parse_epoch(time_text) or 0,
                "result": result,
                "language": language,
                "exec_ms": exec_ms,
                "memory_kib": memory_kib,
                "url": urljoin("https://atcoder.jp", submission_href),
            }
        )
    return submissions


class _NextPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.next_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self.next_href is not None:
            return
        attrs_dict = {key: value for key, value in attrs}
        if attrs_dict.get("rel") == "next" and attrs_dict.get("href"):
            self.next_href = attrs_dict["href"]


def find_next_page_url(html: str, base_url: str) -> str | None:
    parser = _NextPageParser()
    parser.feed(html)
    if parser.next_href:
        return urljoin(base_url, parser.next_href)
    return None


def crawl_submissions_me(
    fetch_html: Callable[[str], str],
    conn,
    contest_id: str,
    user_id: str,
) -> dict:
    contest_uid = atcoder_oj.contest_uid(contest_id)
    state = get_sync_state(conn, user_id, atcoder_oj.name, contest_uid) or {}
    last_submission_id = state.get("last_submission_id")
    if last_submission_id is not None:
        try:
            last_submission_id = int(last_submission_id)
        except ValueError:
            last_submission_id = None
    known_problems = list_problem_uids_by_contest(conn, contest_uid)
    base_url = f"https://atcoder.jp/contests/{contest_id}/submissions/me"
    url = base_url
    all_new = []
    while url:
        html = fetch_html(url)
        if detect_login_required(html):
            raise RuntimeError("login required")
        submissions = parse_submissions_me(html, contest_id, user_id)
        if last_submission_id is not None:
            submissions = [s for s in submissions if s["submission_id"] > last_submission_id]
        submissions = [s for s in submissions if s["problem_uid"] in known_problems]
        all_new.extend(submissions)
        next_url = find_next_page_url(html, url)
        if not next_url or not submissions or next_url == url:
            break
        url = next_url
    stats = {"inserted": 0, "updated": 0}
    if all_new:
        all_new.sort(key=lambda s: s["submission_id"])
        stats = upsert_submissions_with_stats(conn, all_new)
        latest = all_new[-1]
        upsert_sync_state(
            conn,
            user_id,
            atcoder_oj.name,
            contest_uid,
            str(latest["submission_id"]),
            latest.get("epoch_second"),
        )
    else:
        ensure_sync_state(conn, user_id, atcoder_oj.name, contest_uid)
    return stats
