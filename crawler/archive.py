from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from crawler.html_table import parse_first_table
from db.dao import upsert_contests
from oj.atcoder import atcoder_oj

JST = timezone(timedelta(hours=9))


def _parse_start_epoch(text: str) -> int | None:
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


def _parse_duration_sec(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) == 2:
        hours, minutes = parts
        return int(hours) * 3600 + int(minutes) * 60
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return None


def parse_archive(html: str, category: str | None = None) -> list[dict]:
    rows = parse_first_table(html)
    contests = []
    for row in rows:
        if len(row) < 4:
            continue
        links = row[1].get("links", [])
        if not links:
            continue
        contest_url = links[0]
        contest_id = contest_url.strip("/").split("/")[-1]
        contests.append(
            {
                "contest_uid": atcoder_oj.contest_uid(contest_id),
                "oj": atcoder_oj.name,
                "contest_id": contest_id,
                "title": row[1].get("text"),
                "start_epoch": _parse_start_epoch(row[0].get("text", "")),
                "duration_sec": _parse_duration_sec(row[2].get("text", "")),
                "rated_range": row[3].get("text") or None,
                "category": category,
            }
        )
    return contests


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


class _PageLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.hrefs.append(value)


def find_next_page_url(html: str, base_url: str) -> str | None:
    parser = _NextPageParser()
    parser.feed(html)
    if parser.next_href:
        next_url = urljoin(base_url, parser.next_href)
        base_parsed = urlparse(base_url)
        next_parsed = urlparse(next_url)
        base_query = parse_qs(base_parsed.query)
        next_query = parse_qs(next_parsed.query)
        changed = False
        for key, value in base_query.items():
            if key not in next_query:
                next_query[key] = value
                changed = True
        if changed:
            merged_query = urlencode(next_query, doseq=True)
            return urlunparse(next_parsed._replace(query=merged_query))
        return next_url
    current_page = 1
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    if "page" in query:
        try:
            current_page = int(query["page"][0])
        except (ValueError, IndexError):
            current_page = 1
    link_parser = _PageLinkParser()
    link_parser.feed(html)
    pages = set()
    for href in link_parser.hrefs:
        if "page=" not in href:
            continue
        try:
            page = int(href.split("page=", 1)[1].split("&", 1)[0])
        except ValueError:
            continue
        pages.add(page)
    if (current_page + 1) in pages:
        query["page"] = [str(current_page + 1)]
        next_query = urlencode(query, doseq=True)
        next_url = urlunparse(parsed._replace(query=next_query))
        return next_url
    return None


def crawl_archive(
    fetch_html: Callable[[str], str],
    conn,
    start_url: str,
    category: str | None = None,
    filter_fn: Callable[[dict], bool] | None = None,
) -> int:
    url = start_url
    total = 0
    while url:
        html = fetch_html(url)
        contests = parse_archive(html, category=category)
        if filter_fn:
            contests = [c for c in contests if filter_fn(c)]
        total += upsert_contests(conn, contests)
        next_url = find_next_page_url(html, url)
        if next_url == url:
            break
        url = next_url
    return total
