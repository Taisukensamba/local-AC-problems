from __future__ import annotations

from typing import Callable
from config.loader import AppConfig, ConfigError
from crawler.http import FetchError, LoginRequiredError
from db.dao import ensure_sync_state
from db.queries import list_contest_uids
from crawler.cookie_auth import build_cookie_header, require_revel_session
from crawler.submissions_api import sync_submissions_api
from crawler.submissions_me import crawl_submissions_me
from oj.atcoder import atcoder_oj, contest_id_from_uid


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

    if config.atcoder.sync.mode in ("api", "hybrid"):
        stats["api"] = sync_submissions_api(fetch_json, conn, config.atcoder.user_id)

    if config.atcoder.sync.mode in ("cookie", "hybrid"):
        try:
            revel = require_revel_session(config)
        except ConfigError as exc:
            stats["errors"].append(str(exc))
        else:
            headers = {"Cookie": build_cookie_header(revel)}
            if contest_ids is None:
                contest_ids = list_contest_uids(conn, atcoder_oj.name)
            total = len(contest_ids)
            done = 0
            failure_streak = 0
            for contest_uid in contest_ids:
                contest_id = contest_id_from_uid(contest_uid)
                try:
                    result = crawl_submissions_me(
                        lambda url: fetch_html(url, headers),
                        conn,
                        contest_id,
                        config.atcoder.user_id,
                    )
                    if result.get("skipped"):
                        stats["errors"].append(f"skip {contest_id}: tasks not synced")
                        done += 1
                        if on_progress:
                            on_progress(contest_id, done, total)
                        continue
                except LoginRequiredError as exc:
                    stats["errors"].append(str(exc))
                    raise
                except FetchError as exc:
                    if exc.status == 404:
                        stats["errors"].append(f"skip {contest_id}: 404")
                        ensure_sync_state(conn, config.atcoder.user_id, atcoder_oj.name, contest_uid)
                        failure_streak = 0
                    else:
                        failure_streak += 1
                        detail = exc.kind
                        if exc.status is not None:
                            detail = f"{detail} {exc.status}"
                        stats["errors"].append(f"error {contest_id}: {detail}")
                        if failure_streak >= 10:
                            raise
                    done += 1
                    if on_progress:
                        on_progress(contest_id, done, total)
                    continue
                else:
                    failure_streak = 0
                stats["cookie"]["inserted"] += result["inserted"]
                stats["cookie"]["updated"] += result["updated"]
                done += 1
                if on_progress:
                    on_progress(contest_id, done, total)
    return stats
