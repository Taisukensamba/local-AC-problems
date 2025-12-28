from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlencode
from urllib.error import HTTPError


def build_recent_url(user_id: str, page: int, mode: str) -> str:
    if mode == "user":
        params = urlencode({"page": page})
        return f"https://atcoder.jp/users/{user_id}/submissions?{params}"
    params = urlencode({"f.User": user_id, "page": page})
    return f"https://atcoder.jp/submissions?{params}"


class _SubmissionsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, int]] = []
        self._pattern = re.compile(r"^/contests/([^/]+)/submissions/(\d+)$")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = None
        for key, value in attrs:
            if key == "href":
                href = value
                break
        if not href:
            return
        match = self._pattern.match(href)
        if match:
            contest_id = match.group(1)
            submission_id = int(match.group(2))
            self.items.append((contest_id, submission_id))


def parse_recent_submissions(html: str) -> list[tuple[str, int]]:
    parser = _SubmissionsParser()
    parser.feed(html)
    return parser.items


def list_updated_contests(
    fetch_html: Callable[[str], str],
    user_id: str,
    last_submission_id: int,
    max_pages: int = 5,
) -> list[str]:
    contests = set()
    seen_any = False
    modes = ["global", "user"]
    for mode in modes:
        for page in range(1, max_pages + 1):
            url = build_recent_url(user_id, page, mode)
            try:
                html = fetch_html(url)
            except HTTPError as exc:
                if exc.code == 404:
                    break
                raise
            items = parse_recent_submissions(html)
            if not items:
                break
            for contest_id, submission_id in items:
                if submission_id <= last_submission_id:
                    seen_any = True
                    continue
                contests.add(contest_id)
            if seen_any:
                break
        if contests:
            break
    return sorted(contests)
