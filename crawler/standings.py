from __future__ import annotations

import json
import sys
import time
from http.cookiejar import Cookie, LWPCookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

DEFAULT_BASE_DIR = Path("json")
DEFAULT_COOKIE_JAR = DEFAULT_BASE_DIR / "cookies.lwp"
USER_AGENT = "AC-problems/0.1 (+https://github.com/your-org/ac-problems)"


def _standings_path(contest_category: str, contest_slug: str, base_dir: Path) -> Path:
    return base_dir / contest_category / f"{contest_slug}.json"


def _standings_url(contest_slug: str) -> str:
    return f"https://atcoder.jp/contests/{contest_slug}/standings/json"


def _load_cookie_jar(path: Path) -> LWPCookieJar:
    jar = LWPCookieJar(str(path))
    if path.exists():
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except Exception as exc:
            print(f"cookie-jar: load failed ({exc})", file=sys.stderr)
    return jar


def _save_cookie_jar(jar: LWPCookieJar) -> None:
    try:
        jar.save(ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        print(f"cookie-jar: save failed ({exc})", file=sys.stderr)


def _looks_like_html(text: str) -> bool:
    head = text.lstrip()[:200].lower()
    return head.startswith("<!doctype") or head.startswith("<html") or "<html" in head


def _add_revel_cookie(jar: LWPCookieJar, revel_session: str) -> None:
    cookie = Cookie(
        version=0,
        name="REVEL_SESSION",
        value=revel_session,
        port=None,
        port_specified=False,
        domain="atcoder.jp",
        domain_specified=True,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=False,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None},
        rfc2109=False,
    )
    jar.set_cookie(cookie)


def get_standings(
    contest_slug: str,
    contest_category: str,
    base_dir: Path | str = DEFAULT_BASE_DIR,
    cookie_jar_path: Path | str = DEFAULT_COOKIE_JAR,
    revel_session: str | None = None,
    timeout_sec: int = 20,
    sleep_sec: int = 0,
    retry_429: int = 3,
) -> dict:
    base_dir = Path(base_dir)
    cookie_jar_path = Path(cookie_jar_path)
    path = _standings_path(contest_category, contest_slug, base_dir)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = f.read()
            if _looks_like_html(raw):
                print(f"standings: html cached {path}", file=sys.stderr)
                path.unlink(missing_ok=True)
            else:
                return json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"standings: invalid json {path} ({exc})", file=sys.stderr)
            path.unlink(missing_ok=True)

    url = _standings_url(contest_slug)
    cookie_jar_path.parent.mkdir(parents=True, exist_ok=True)
    jar = _load_cookie_jar(cookie_jar_path)
    if revel_session:
        _add_revel_cookie(jar, revel_session)
    opener = build_opener(HTTPCookieProcessor(jar))
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    attempt = 0
    while True:
        try:
            with opener.open(req, timeout=timeout_sec) as res:
                raw = res.read().decode("utf-8")
            break
        except HTTPError as exc:
            attempt += 1
            if exc.code == 429 and attempt <= retry_429:
                wait = 30 * attempt
                print(
                    f"standings: rate limited {contest_slug} (retry {attempt}/{retry_429})",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            print(f"standings: fetch failed {contest_slug} ({exc.code})", file=sys.stderr)
            raise
        except URLError as exc:
            print(f"standings: fetch failed {contest_slug} ({exc})", file=sys.stderr)
            raise

    try:
        if _looks_like_html(raw):
            raise json.JSONDecodeError("html response", raw, 0)
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"standings: invalid json {contest_slug} ({exc})", file=sys.stderr)
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed), encoding="utf-8")
    _save_cookie_jar(jar)
    if sleep_sec:
        time.sleep(sleep_sec)
    return parsed
