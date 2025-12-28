from __future__ import annotations

from typing import Callable
from urllib.error import HTTPError

from config.loader import AppConfig, ConfigError
from db.dao import ensure_sync_state
from db.queries import list_contest_ids
from crawler.cookie_auth import build_cookie_header, require_revel_session
from crawler.submissions_api import sync_submissions_api
from crawler.submissions_me import crawl_submissions_me


def run_sync(
    config: AppConfig,
    conn,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str, dict | None], str],
    contest_ids: list[str] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    stats = {
        "api": {"inserted": 0, "updated": 0},
        "cookie": {"inserted": 0, "updated": 0},
        "errors": [],
    }

    if config.sync.mode in ("api", "hybrid"):
        stats["api"] = sync_submissions_api(fetch_json, conn, config.user_id)

    if config.sync.mode in ("cookie", "hybrid"):
        try:
            revel = require_revel_session(config)
        except ConfigError as exc:
            stats["errors"].append(str(exc))
        else:
            headers = {"Cookie": build_cookie_header(revel)}
            if contest_ids is None:
                contest_ids = list_contest_ids(conn)
            total = len(contest_ids)
            done = 0
            for contest_id in contest_ids:
                try:
                    result = crawl_submissions_me(
                        lambda url: fetch_html(url, headers),
                        conn,
                        contest_id,
                        config.user_id,
                    )
                except HTTPError as exc:
                    if exc.code == 404:
                        stats["errors"].append(f"skip {contest_id}: 404")
                        ensure_sync_state(conn, config.user_id, contest_id)
                        done += 1
                        if on_progress:
                            on_progress(contest_id, done, total)
                        continue
                    raise
                stats["cookie"]["inserted"] += result["inserted"]
                stats["cookie"]["updated"] += result["updated"]
                done += 1
                if on_progress:
                    on_progress(contest_id, done, total)
    return stats
