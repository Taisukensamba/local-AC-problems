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
from crawler.http import HttpClient, cache_config_from_app
from crawler.sync import run_sync
from db.queries import list_contest_ids
from crawler.tasks import crawl_tasks
from db.queries import (
    list_contest_ids,
    list_contests_by_prefix,
    list_contests_missing_submissions,
    list_contests_missing_tasks,
    problems_by_contest,
    progress_summary,
    recent_submissions,
    search_problems,
)
from db.schema import connect, init_db

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
    exclude_ahc: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user_id = app.state.config.user_id
    return _with_conn(
        lambda conn: search_problems(
            conn,
            user_id,
            status,
            minDiff,
            maxDiff,
            query,
            contest,
            exclude_ahc,
            limit,
            offset,
        )
    )


@app.get("/api/progress/summary")
def get_progress_summary() -> list[dict]:
    return _with_conn(lambda conn: progress_summary(conn, app.state.config.user_id))


@app.get("/api/progress/recent")
def get_progress_recent(limit: int = Query(default=10, ge=1, le=50)) -> list[dict]:
    return _with_conn(lambda conn: recent_submissions(conn, app.state.config.user_id, limit))


@app.get("/api/me")
def get_me() -> dict:
    return {"user_id": app.state.config.user_id}


def _contests_with_problems(contest_ids: list[str]) -> list[dict]:
    def load(conn) -> dict[str, list[dict]]:
        return problems_by_contest(conn, app.state.config.user_id, contest_ids)

    grouped = _with_conn(load)
    return [
        {"contest_id": contest_id, "problems": grouped.get(contest_id, [])}
        for contest_id in contest_ids
    ]


def _contests_by_prefix(prefix: str, limit: int, offset: int) -> list[dict]:
    contest_ids = _with_conn(lambda conn: list_contests_by_prefix(conn, prefix, limit, offset))
    return _contests_with_problems(contest_ids)


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


@app.get("/api/contests/ahc")
def get_ahc_contests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _contests_by_prefix("ahc", limit, offset)


def _build_client(config) -> HttpClient:
    return HttpClient(config.rate_limit, cache_config_from_app(config))


def _sync_contests(conn, status: dict, fetch_html: Callable[[str], str]) -> int:
    _set_progress(status, "contest")
    base_url = "https://atcoder.jp/contests/archive?lang=ja"
    allowed_prefixes = ("abc", "arc", "agc", "ahc")
    return crawl_archive(
        fetch_html,
        conn,
        base_url,
        filter_fn=lambda c: c["contest_id"].startswith(allowed_prefixes),
    )


def _sync_tasks(conn, status: dict, fetch_html: Callable[[str], str], payload: dict) -> dict:
    contest_ids = payload.get("contest_ids") or list_contest_ids(conn)
    if payload.get("tasks_incremental"):
        contest_ids = list_contests_missing_tasks(conn, contest_ids)
    _set_progress(status, "tasks", total=len(contest_ids))

    total = 0
    skipped = []
    for contest_id in contest_ids:
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
            contest_ids = list_contest_ids(conn)
    if contest_ids is None:
        contest_ids = list_contest_ids(conn)

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
                config = replace(config, sync=replace(config.sync, mode=mode))

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
