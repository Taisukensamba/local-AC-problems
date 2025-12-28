import json
import tempfile
import unittest

from crawler.submissions_api import build_api_url, parse_submissions, sync_submissions_api
from db.dao import upsert_contests, upsert_problems
from db.schema import connect, init_db
from oj.atcoder import atcoder_oj


class SubmissionsApiTest(unittest.TestCase):
    def test_build_api_url(self) -> None:
        url = build_api_url("alice", 100)
        self.assertIn("user=alice", url)
        self.assertIn("from_second=100", url)

    def test_parse_submissions(self) -> None:
        payload = json.dumps(
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
        items = parse_submissions(payload)
        self.assertEqual(items[0]["submission_uid"], atcoder_oj.submission_uid(1))
        self.assertEqual(items[0]["url"], "https://atcoder.jp/contests/abc100/submissions/1")

    def test_sync_submissions(self) -> None:
        payload = json.dumps(
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

        def fetch(_url: str) -> str:
            return payload

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
                            "title": "Sample Problem",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": None,
                            "solved_count": None,
                            "tags_json": None,
                            "updated_epoch": 2,
                        }
                    ],
                )
                stats = sync_submissions_api(fetch, conn, "alice")
                conn.commit()
                self.assertEqual(stats["inserted"], 1)
            finally:
                conn.close()
