import sqlite3
import tempfile
import unittest

from db.dao import get_latest_submission_epoch, upsert_contests, upsert_problems, upsert_submissions
from db.schema import init_db


class DaoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.NamedTemporaryFile(suffix=".db")
        init_db(self.temp.name)
        self.conn = sqlite3.connect(self.temp.name)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.close()

    def test_upsert_contest(self) -> None:
        count = upsert_contests(
            self.conn,
            [
                {
                    "contest_id": "abc001",
                    "title": "Sample Contest",
                    "start_epoch": 1,
                    "duration_sec": 600,
                    "rated_range": "0-1999",
                    "category": "abc",
                }
            ],
        )
        self.conn.commit()
        self.assertEqual(count, 1)
        row = self.conn.execute(
            "SELECT title, duration_sec FROM contests WHERE contest_id = ?", ("abc001",)
        ).fetchone()
        self.assertEqual(row, ("Sample Contest", 600))

    def test_upsert_problem(self) -> None:
        upsert_contests(
            self.conn,
            [
                {
                    "contest_id": "abc001",
                    "title": "Sample Contest",
                    "start_epoch": 1,
                    "duration_sec": 600,
                    "rated_range": "0-1999",
                    "category": "abc",
                }
            ],
        )
        count = upsert_problems(
            self.conn,
            [
                {
                    "problem_id": "abc001_a",
                    "contest_id": "abc001",
                    "task_index": "A",
                    "title": "Sample Problem",
                    "point": 100,
                    "url": "https://atcoder.jp/contests/abc001/tasks/abc001_1",
                    "difficulty": None,
                    "updated_epoch": 2,
                }
            ],
        )
        self.conn.commit()
        self.assertEqual(count, 1)
        row = self.conn.execute(
            "SELECT title, task_index FROM problems WHERE problem_id = ?", ("abc001_a",)
        ).fetchone()
        self.assertEqual(row, ("Sample Problem", "A"))

    def test_upsert_submission(self) -> None:
        upsert_contests(
            self.conn,
            [
                {
                    "contest_id": "abc001",
                    "title": "Sample Contest",
                    "start_epoch": 1,
                    "duration_sec": 600,
                    "rated_range": "0-1999",
                    "category": "abc",
                }
            ],
        )
        upsert_problems(
            self.conn,
            [
                {
                    "problem_id": "abc001_a",
                    "contest_id": "abc001",
                    "task_index": "A",
                    "title": "Sample Problem",
                    "point": 100,
                    "url": "https://atcoder.jp/contests/abc001/tasks/abc001_1",
                    "difficulty": None,
                    "updated_epoch": 2,
                }
            ],
        )
        count = upsert_submissions(
            self.conn,
            [
                {
                    "submission_id": 10,
                    "problem_id": "abc001_a",
                    "user_id": "alice",
                    "epoch_second": 123,
                    "result": "AC",
                    "language": "Python",
                    "exec_ms": 50,
                    "memory_kib": 1024,
                    "url": "https://atcoder.jp/contests/abc001/submissions/10",
                }
            ],
        )
        self.conn.commit()
        self.assertEqual(count, 1)
        row = self.conn.execute(
            "SELECT result, language FROM submissions WHERE submission_id = ?", (10,)
        ).fetchone()
        self.assertEqual(row, ("AC", "Python"))

    def test_latest_submission_epoch(self) -> None:
        upsert_contests(
            self.conn,
            [
                {
                    "contest_id": "abc001",
                    "title": "Sample Contest",
                    "start_epoch": 1,
                    "duration_sec": 600,
                    "rated_range": "0-1999",
                    "category": "abc",
                }
            ],
        )
        upsert_problems(
            self.conn,
            [
                {
                    "problem_id": "abc001_a",
                    "contest_id": "abc001",
                    "task_index": "A",
                    "title": "Sample Problem",
                    "point": 100,
                    "url": "https://atcoder.jp/contests/abc001/tasks/abc001_1",
                    "difficulty": None,
                    "updated_epoch": 2,
                }
            ],
        )
        upsert_submissions(
            self.conn,
            [
                {
                    "submission_id": 10,
                    "problem_id": "abc001_a",
                    "user_id": "alice",
                    "epoch_second": 123,
                    "result": "WA",
                    "language": "Python",
                    "exec_ms": 50,
                    "memory_kib": 1024,
                    "url": "https://atcoder.jp/contests/abc001/submissions/10",
                },
                {
                    "submission_id": 11,
                    "problem_id": "abc001_a",
                    "user_id": "alice",
                    "epoch_second": 200,
                    "result": "AC",
                    "language": "Python",
                    "exec_ms": 60,
                    "memory_kib": 1024,
                    "url": "https://atcoder.jp/contests/abc001/submissions/11",
                },
            ],
        )
        self.conn.commit()
        self.assertEqual(get_latest_submission_epoch(self.conn, "alice"), 200)
