import json
import pathlib
import tempfile
import unittest
from urllib.error import HTTPError

from config.loader import (
    AppConfig,
    AtCoderConfig,
    CacheConfig,
    CodeforcesConfig,
    CookieConfig,
    DifficultyConfig,
    RateLimitConfig,
    SyncConfig,
)
from crawler.sync import run_sync
from db.dao import upsert_contests, upsert_problems
from db.schema import connect, init_db
from oj.atcoder import atcoder_oj


class SyncTest(unittest.TestCase):
    def test_run_sync_hybrid(self) -> None:
        api_payload = json.dumps(
            [
                {
                    "id": 1,
                    "epoch_second": 123,
                    "problem_id": "abc100_a",
                    "contest_id": "abc100",
                    "user_id": "alice",
                    "result": "AC",
                    "language": "Python",
                    "execution_time": 50,
                    "memory": 1024,
                }
            ]
        )
        pages = {
            "https://atcoder.jp/contests/abc100/submissions/me": pathlib.Path(
                "data/fixtures/submissions_me_page1.html"
            ).read_text(encoding="utf-8"),
            "https://atcoder.jp/contests/abc100/submissions/me?page=2": pathlib.Path(
                "data/fixtures/submissions_me_page2.html"
            ).read_text(encoding="utf-8"),
        }

        def fetch_json(_url: str) -> str:
            return api_payload

        def fetch_html(url: str, _headers: dict | None) -> str:
            return pages[url]

        config = AppConfig(
            atcoder=AtCoderConfig(
                user_id="alice",
                sync=SyncConfig(mode="hybrid"),
                difficulty=DifficultyConfig(source_url="https://example.com"),
                cookie=CookieConfig(revel_session="abc"),
            ),
            codeforces=CodeforcesConfig(handle="alice_cf", include_gym=False),
            rate_limit=RateLimitConfig(atcoder_rps=1.0, codeforces_min_interval_seconds=2.0),
            cache=CacheConfig(enabled=True, ttl_sec=3600, dir_path="data/cache"),
        )

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "oj": atcoder_oj.name,
                            "contest_id": "abc100",
                            "title": "Sample Contest",
                            "start_epoch": 1,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        }
                    ],
                )
                upsert_problems(
                    conn,
                    [
                        {
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                            ),
                            "oj": atcoder_oj.name,
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "contest_id": "abc100",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": None,
                            "solved_count": None,
                            "tags_json": None,
                            "updated_epoch": None,
                        },
                        {
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="B", name=None, problem_id="abc100_b"
                            ),
                            "oj": atcoder_oj.name,
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "contest_id": "abc100",
                            "task_index": "B",
                            "title": "Beta",
                            "point": 200,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_b",
                            "difficulty": None,
                            "solved_count": None,
                            "tags_json": None,
                            "updated_epoch": None,
                        },
                    ],
                )
                stats = run_sync(
                    config,
                    conn,
                    fetch_json,
                    fetch_html,
                    [atcoder_oj.contest_uid("abc100")],
                )
                conn.commit()
                self.assertEqual(stats["api"]["inserted"], 1)
                self.assertEqual(stats["cookie"]["inserted"], 3)
                self.assertEqual(stats["errors"], [])
            finally:
                conn.close()

    def test_run_sync_cookie_all_contests(self) -> None:
        html = pathlib.Path("data/fixtures/submissions_me_page1.html").read_text(encoding="utf-8")

        def fetch_json(_url: str) -> str:
            return "[]"

        def fetch_html(_url: str, _headers: dict | None) -> str:
            return html

        config = AppConfig(
            atcoder=AtCoderConfig(
                user_id="alice",
                sync=SyncConfig(mode="cookie"),
                difficulty=DifficultyConfig(source_url="https://example.com"),
                cookie=CookieConfig(revel_session="abc"),
            ),
            codeforces=CodeforcesConfig(handle="alice_cf", include_gym=False),
            rate_limit=RateLimitConfig(atcoder_rps=1.0, codeforces_min_interval_seconds=2.0),
            cache=CacheConfig(enabled=True, ttl_sec=3600, dir_path="data/cache"),
        )

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "oj": atcoder_oj.name,
                            "contest_id": "abc100",
                            "title": "Sample Contest",
                            "start_epoch": 1,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        }
                    ],
                )
                upsert_problems(
                    conn,
                    [
                        {
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                            ),
                            "oj": atcoder_oj.name,
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "contest_id": "abc100",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": None,
                            "solved_count": None,
                            "tags_json": None,
                            "updated_epoch": None,
                        }
                    ],
                )
                upsert_problems(
                    conn,
                    [
                        {
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="B", name=None, problem_id="abc100_b"
                            ),
                            "oj": atcoder_oj.name,
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "contest_id": "abc100",
                            "task_index": "B",
                            "title": "Beta",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_b",
                            "difficulty": None,
                            "solved_count": None,
                            "tags_json": None,
                            "updated_epoch": None,
                        }
                    ],
                )
                stats = run_sync(config, conn, fetch_json, fetch_html, None)
                conn.commit()
                self.assertEqual(stats["cookie"]["inserted"], 4)
            finally:
                conn.close()

    def test_run_sync_skips_404(self) -> None:
        def fetch_json(_url: str) -> str:
            return "[]"

        def fetch_html(_url: str, _headers: dict | None) -> str:
            raise HTTPError(_url, 404, "Not Found", None, None)

        config = AppConfig(
            atcoder=AtCoderConfig(
                user_id="alice",
                sync=SyncConfig(mode="cookie"),
                difficulty=DifficultyConfig(source_url="https://example.com"),
                cookie=CookieConfig(revel_session="abc"),
            ),
            codeforces=CodeforcesConfig(handle="alice_cf", include_gym=False),
            rate_limit=RateLimitConfig(atcoder_rps=1.0, codeforces_min_interval_seconds=2.0),
            cache=CacheConfig(enabled=True, ttl_sec=3600, dir_path="data/cache"),
        )

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
                            "contest_uid": atcoder_oj.contest_uid("abc100"),
                            "oj": atcoder_oj.name,
                            "contest_id": "abc100",
                            "title": "Sample Contest",
                            "start_epoch": 1,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        }
                    ],
                )
                conn.commit()
                stats = run_sync(config, conn, fetch_json, fetch_html, None)
                self.assertEqual(stats["cookie"]["inserted"], 0)
                self.assertTrue(any("skip abc100" in err for err in stats["errors"]))
            finally:
                conn.close()
