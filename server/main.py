from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.loader import ConfigError, load_config
from crawler.archive import crawl_archive
from crawler.codeforces_api import (
    sync_contests as sync_codeforces_contests,
    sync_contest_tasks as sync_codeforces_contest_tasks,
    sync_problemset as sync_codeforces_problemset,
    sync_user_status as sync_codeforces_user_status,
)
from crawler.http import AdaptiveHttpClient, HttpClient, cache_config_from_app
from crawler.sync import run_sync
from crawler.tasks import crawl_tasks
from db.queries import (
    list_contest_uids,
    list_contest_uids_by_category,
    list_contest_uids_by_prefix,
    list_contests_missing_submissions,
    list_contests_missing_tasks,
    get_contest_titles,
    problems_by_contest,
    progress_summary,
    recent_submissions,
    search_problems,
)
from db.schema import connect, init_db
from db.dao import get_sync_state
from oj.atcoder import atcoder_oj
from oj.codeforces import codeforces_oj

app = FastAPI()
UI_DIR = Path(__file__).resolve().parent.parent / "ui"
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


def _with_conn(fn: Callable[[Any], Any]) -> Any:
    conn = connect()
    try:
        return fn(conn)
    finally:
        conn.close()


def _init_sync_status() -> dict:
    return {
        "running": False,
        "started_at": None,
        "finished_at": None,
        "last_result": None,
        "last_error": None,
        "progress": None,
    }


def _init_sync_all_status() -> dict:
    return {
        "running": False,
        "started_at": None,
        "finished_at": None,
        "last_error": None,
    }


def _set_progress(status: dict, phase: str, total: int | None = None) -> None:
    status["progress"] = {"phase": phase, "total": total, "done": 0, "current": None}


@app.on_event("startup")
def load_settings() -> None:
    try:
        app.state.config = load_config()
        init_db()
        app.state.sync_status = _init_sync_status()
        app.state.sync_all_status = _init_sync_all_status()
    except ConfigError as exc:
        raise RuntimeError(str(exc)) from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/api/problems")
def get_problems(
    status: str | None = Query(default=None, pattern="^(solved|unsolved)?$"),
    minDiff: int | None = None,
    maxDiff: int | None = None,
    query: str | None = None,
    contest: str | None = None,
    oj: str | None = Query(default="all"),
    tag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user_id = app.state.config.atcoder.user_id
    return _with_conn(
        lambda conn: search_problems(
            conn,
            user_id,
            status,
            minDiff,
            maxDiff,
            query,
            contest,
            oj,
            tag,
            limit,
            offset,
        )
    )


@app.get("/api/progress/summary")
def get_progress_summary(oj: str | None = Query(default="all")) -> list[dict]:
    return _with_conn(
        lambda conn: progress_summary(conn, app.state.config.atcoder.user_id, oj)
    )


@app.get("/api/progress/recent")
def get_progress_recent(
    limit: int = Query(default=10, ge=1, le=50),
    oj: str | None = Query(default="all"),
) -> list[dict]:
    return _with_conn(
        lambda conn: recent_submissions(conn, app.state.config.atcoder.user_id, limit, oj)
    )


@app.get("/api/me")
def get_me() -> dict:
    return {
        "atcoder_user_id": app.state.config.atcoder.user_id,
        "codeforces_handle": app.state.config.codeforces.handle,
    }


def _contest_id_from_uid(contest_uid: str) -> str:
    if ":" in contest_uid:
        return contest_uid.split(":", 1)[1]
    return contest_uid


def _codeforces_missing_task_contest_ids(conn) -> list[str]:
    categories = [
        "cf-ecr",
        "cf-global",
        "cf-div1+2",
        "cf-div1",
        "cf-div2",
        "cf-div3",
        "cf-div4",
    ]
    missing: list[str] = []
    for category in categories:
        contest_uids = list_contest_uids_by_category(
            conn, codeforces_oj.name, category, 10000, 0
        )
        missing_uids = list_contests_missing_tasks(conn, contest_uids)
        missing.extend(_contest_id_from_uid(uid) for uid in missing_uids)
    return sorted(set(missing))


def _contests_with_problems(contest_uids: list[str]) -> list[dict]:
    def load(conn) -> tuple[dict[str, list[dict]], dict[str, str]]:
        return (
            problems_by_contest(conn, app.state.config.atcoder.user_id, contest_uids),
            get_contest_titles(conn, contest_uids),
        )

    grouped, titles = _with_conn(load)
    return [
        {
            "contest_uid": contest_uid,
            "contest_id": _contest_id_from_uid(contest_uid),
            "contest_title": titles.get(contest_uid),
            "problems": grouped.get(contest_uid, []),
        }
        for contest_uid in contest_uids
    ]


def _contests_by_prefix(prefix: str, limit: int, offset: int) -> list[dict]:
    contest_uids = _with_conn(
        lambda conn: list_contest_uids_by_prefix(conn, prefix, limit, offset)
    )
    return _contests_with_problems(contest_uids)


def _contests_by_category(oj: str, category: str, limit: int, offset: int) -> list[dict]:
    contest_uids = _with_conn(
        lambda conn: list_contest_uids_by_category(conn, oj, category, limit, offset)
    )
    return _contests_with_problems(contest_uids)


@app.get("/api/contests/abc")
def get_abc_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_prefix("abc", limit, offset)


@app.get("/api/contests/arc")
def get_arc_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_prefix("arc", limit, offset)


@app.get("/api/contests/agc")
def get_agc_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_prefix("agc", limit, offset)


@app.get("/api/contests/cf-ecr")
def get_cf_ecr_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-ecr", limit, offset)


@app.get("/api/contests/cf-global")
def get_cf_global_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-global", limit, offset)


@app.get("/api/contests/cf-div1+2")
def get_cf_div1_2_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-div1+2", limit, offset)


@app.get("/api/contests/cf-div1")
def get_cf_div1_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-div1", limit, offset)


@app.get("/api/contests/cf-div2")
def get_cf_div2_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-div2", limit, offset)


@app.get("/api/contests/cf-div3")
def get_cf_div3_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-div3", limit, offset)


@app.get("/api/contests/cf-div4")
def get_cf_div4_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_category(codeforces_oj.name, "cf-div4", limit, offset)


def _build_client(config) -> AdaptiveHttpClient:
    return AdaptiveHttpClient(cache_config_from_app(config))


def _build_codeforces_client(config) -> HttpClient:
    rps = 1.0 / config.rate_limit.codeforces_min_interval_seconds
    return HttpClient(rps, cache_config_from_app(config))


def _sync_contests(conn, status: dict, fetch_html: Callable[[str], str]) -> int:
    _set_progress(status, "contest")
    base_url = "https://atcoder.jp/contests/archive?lang=ja"
    allowed_prefixes = ("abc", "arc", "agc")
    return crawl_archive(
        fetch_html,
        conn,
        base_url,
        filter_fn=lambda c: c["contest_id"].startswith(allowed_prefixes),
    )


def _sync_tasks(conn, status: dict, fetch_html: Callable[[str], str], payload: dict) -> dict:
    contest_ids = payload.get("contest_ids")
    if contest_ids:
        contest_uids = [atcoder_oj.contest_uid(cid) for cid in contest_ids]
    else:
        contest_uids = list_contest_uids(conn, atcoder_oj.name)
    if payload.get("tasks_incremental"):
        contest_uids = list_contests_missing_tasks(conn, contest_uids)
    _set_progress(status, "tasks", total=len(contest_uids))

    total = 0
    skipped = []
    for contest_uid in contest_uids:
        contest_id = _contest_id_from_uid(contest_uid)
        status["progress"]["current"] = contest_id
        try:
            total += crawl_tasks(fetch_html, conn, contest_id)
        except Exception as exc:
            if getattr(exc, "code", None) == 404:
                skipped.append(contest_id)
            else:
                raise
        finally:
            status["progress"]["done"] += 1

    result: dict[str, Any] = {"tasks": total}
    if skipped:
        result["tasks_skipped"] = skipped
    return result


def _sync_submissions(
    conn,
    status: dict,
    config,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str, dict | None], str],
    payload: dict,
) -> dict:
    contest_ids = payload.get("contest_ids")
    if payload.get("submissions_incremental"):
        if contest_ids is None:
            contest_ids = list_contest_uids(conn, atcoder_oj.name)
    if contest_ids is None:
        contest_ids = list_contest_uids(conn, atcoder_oj.name)
    else:
        contest_ids = [
            cid if cid.startswith(f"{atcoder_oj.name}:") else atcoder_oj.contest_uid(cid)
            for cid in contest_ids
        ]

    _set_progress(status, "submissions", total=len(contest_ids))

    def on_progress(current: str, done: int, total: int) -> None:
        status["progress"]["current"] = current
        status["progress"]["done"] = done
        status["progress"]["total"] = total

    return {
        "submissions": run_sync(
            config,
            conn,
            fetch_json,
            fetch_html,
            contest_ids=contest_ids,
            on_progress=on_progress,
        )
    }


@app.post("/api/sync")
def start_sync(payload: dict, background_tasks: BackgroundTasks) -> dict:
    status = app.state.sync_status
    if status["running"]:
        return {"status": "running"}

    def run_task() -> None:
        status.update(_init_sync_status())
        status["running"] = True
        status["started_at"] = datetime.now(timezone.utc).isoformat()
        conn = connect()
        try:
            config = app.state.config
            mode = payload.get("mode")
            if mode:
                config = replace(
                    config,
                    atcoder=replace(
                        config.atcoder, sync=replace(config.atcoder.sync, mode=mode)
                    ),
                )

            client = _build_client(config)
            fetch_json = client.get_text
            fetch_html = client.get_text

            result: dict[str, Any] = {}
            if payload.get("contest"):
                result["contest"] = _sync_contests(conn, status, fetch_html)
            if payload.get("tasks", False):
                result.update(_sync_tasks(conn, status, fetch_html, payload))
            if payload.get("submissions", False):
                result.update(
                    _sync_submissions(conn, status, config, fetch_json, fetch_html, payload)
                )

            conn.commit()
            status["last_result"] = result
        except Exception as exc:
            status["last_error"] = str(exc)
        finally:
            conn.close()
            status["finished_at"] = datetime.now(timezone.utc).isoformat()
            status["running"] = False

    background_tasks.add_task(run_task)
    return {"status": "started"}


@app.post("/api/sync/codeforces/problems")
def start_sync_codeforces_problems(background_tasks: BackgroundTasks) -> dict:
    def run_task() -> None:
        conn = connect()
        try:
            client = _build_codeforces_client(app.state.config)
            result = sync_codeforces_problemset(client.get_text, conn)
            conn.commit()
            app.state.sync_status["last_result"] = {"codeforces_problems": result}
        finally:
            conn.close()

    background_tasks.add_task(run_task)
    return {"status": "started"}


@app.post("/api/sync/codeforces/contests")
def start_sync_codeforces_contests(background_tasks: BackgroundTasks) -> dict:
    def run_task() -> None:
        conn = connect()
        try:
            client = _build_codeforces_client(app.state.config)
            result = sync_codeforces_contests(
                client.get_text, conn, app.state.config.codeforces.include_gym
            )
            missing_contests = _codeforces_missing_task_contest_ids(conn)
            task_result = None
            if missing_contests:
                task_result = sync_codeforces_contest_tasks(
                    client.get_text, conn, missing_contests
                )
            conn.commit()
            payload = {"codeforces_contests": result}
            if task_result is not None:
                payload["codeforces_contest_tasks"] = task_result
            app.state.sync_status["last_result"] = payload
        finally:
            conn.close()

    background_tasks.add_task(run_task)
    return {"status": "started"}


@app.post("/api/sync/codeforces/submissions")
def start_sync_codeforces_submissions(background_tasks: BackgroundTasks) -> dict:
    def run_task() -> None:
        conn = connect()
        try:
            client = _build_codeforces_client(app.state.config)
            fetch_json = lambda url: client.get_text(url, use_cache=False)
            state = get_sync_state(
                conn,
                app.state.config.codeforces.handle,
                codeforces_oj.name,
                "global",
            )
            last_seen = None
            if state and state.get("last_submission_id"):
                try:
                    last_seen = int(state["last_submission_id"])
                except ValueError:
                    last_seen = None
            result = sync_codeforces_user_status(
                fetch_json,
                conn,
                app.state.config.codeforces.handle,
                last_seen,
            )
            conn.commit()
            app.state.sync_status["last_result"] = {"codeforces_submissions": result}
        finally:
            conn.close()

    background_tasks.add_task(run_task)
    return {"status": "started"}


@app.get("/api/sync/status")
def sync_status() -> dict:
    return app.state.sync_status


@app.post("/api/sync/all")
def start_sync_all(background_tasks: BackgroundTasks) -> dict:
    status = app.state.sync_all_status
    if status["running"]:
        return {"status": "running"}

    def run_task() -> None:
        status.update(_init_sync_all_status())
        status["running"] = True
        status["started_at"] = datetime.now(timezone.utc).isoformat()
        root = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        try:
            subprocess.run(
                ["bash", str(root / "scripts" / "sync_all.sh")],
                cwd=root,
                check=True,
                env=env,
            )
        except Exception as exc:
            status["last_error"] = str(exc)
        finally:
            status["finished_at"] = datetime.now(timezone.utc).isoformat()
            status["running"] = False

    background_tasks.add_task(run_task)
    return {"status": "started"}


@app.get("/api/sync/all/status")
def sync_all_status() -> dict:
    return app.state.sync_all_status
