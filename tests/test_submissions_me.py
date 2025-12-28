import pathlib
import tempfile
import unittest

from crawler.submissions_me import crawl_submissions_me, detect_login_required, parse_submissions_me
from db.dao import get_sync_state, list_problem_uids_by_contest, upsert_contests, upsert_problems
from db.schema import connect, init_db
from oj.atcoder import atcoder_oj


class SubmissionsMeTest(unittest.TestCase):
    def test_parse_submissions_me(self) -> None:
        html = pathlib.Path("data/fixtures/submissions_me_page1.html").read_text(encoding="utf-8")
        items = parse_submissions_me(html, "abc100", "alice")
        self.assertEqual(items[0]["submission_id"], 102)
        self.assertEqual(
            items[0]["problem_uid"],
            atcoder_oj.problem_uid(
                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
            ),
        )

    def test_parse_submissions_me_table_v2(self) -> None:
        html = pathlib.Path("data/fixtures/submissions_me_table2.html").read_text(encoding="utf-8")
        items = parse_submissions_me(html, "abc436", "alice")
        self.assertEqual(items[0]["submission_id"], 71687691)
        self.assertEqual(items[0]["result"], "AC")
        self.assertEqual(items[0]["exec_ms"], 1)
        self.assertEqual(items[0]["memory_kib"], 3676)

    def test_detect_login_required(self) -> None:
        html = pathlib.Path("data/fixtures/login_page.html").read_text(encoding="utf-8")
        self.assertTrue(detect_login_required(html))

    def test_crawl_submissions_me_incremental(self) -> None:
        pages = {
            "https://atcoder.jp/contests/abc100/submissions/me": pathlib.Path(
                "data/fixtures/submissions_me_page1.html"
            ).read_text(encoding="utf-8"),
            "https://atcoder.jp/contests/abc100/submissions/me?page=2": pathlib.Path(
                "data/fixtures/submissions_me_page2.html"
            ).read_text(encoding="utf-8"),
        }

        def fetch(url: str) -> str:
            return pages[url]

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
                stats = crawl_submissions_me(fetch, conn, "abc100", "alice")
                conn.commit()
                self.assertEqual(stats["inserted"], 3)
                state = get_sync_state(
                    conn, "alice", atcoder_oj.name, atcoder_oj.contest_uid("abc100")
                )
                self.assertEqual(state["last_submission_id"], "102")
            finally:
                conn.close()

    def test_crawl_submissions_skips_unknown_problems(self) -> None:
        pages = {
            "https://atcoder.jp/contests/abc100/submissions/me": pathlib.Path(
                "data/fixtures/submissions_me_page1.html"
            ).read_text(encoding="utf-8"),
            "https://atcoder.jp/contests/abc100/submissions/me?page=2": pathlib.Path(
                "data/fixtures/submissions_me_page2.html"
            ).read_text(encoding="utf-8"),
        }

        def fetch(url: str) -> str:
            return pages[url]

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
                conn.commit()
                known = list_problem_uids_by_contest(conn, atcoder_oj.contest_uid("abc100"))
                self.assertEqual(
                    known,
                    {
                        atcoder_oj.problem_uid(
                            contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                        )
                    },
                )
                stats = crawl_submissions_me(fetch, conn, "abc100", "alice")
                conn.commit()
                self.assertEqual(stats["inserted"], 2)
                state = get_sync_state(
                    conn, "alice", atcoder_oj.name, atcoder_oj.contest_uid("abc100")
                )
                self.assertIsNotNone(state)
            finally:
                conn.close()
