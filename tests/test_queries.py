import tempfile
import unittest

from db.dao import ensure_sync_state, upsert_contests, upsert_problems, upsert_submissions
from db.queries import (
    list_contests_by_prefix,
    list_contests_missing_tasks,
    list_contests_missing_submissions,
    list_contests_other,
    problems_by_contest,
    progress_summary,
    recent_submissions,
    search_problems,
)
from db.schema import connect, init_db


class QueriesTest(unittest.TestCase):
    def test_search_problems_filters(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
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
                            "problem_id": "abc100_a",
                            "contest_id": "abc100",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": 200,
                            "updated_epoch": 2,
                        },
                        {
                            "problem_id": "abc100_b",
                            "contest_id": "abc100",
                            "task_index": "B",
                            "title": "Beta",
                            "point": 200,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_b",
                            "difficulty": 400,
                            "updated_epoch": 2,
                        },
                    ],
                )
                upsert_submissions(
                    conn,
                    [
                        {
                            "submission_id": 1,
                            "problem_id": "abc100_a",
                            "user_id": "alice",
                            "epoch_second": 100,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/1",
                        }
                    ],
                )
                conn.commit()
                solved = search_problems(conn, "alice", "solved", None, None, None, None, 50, 0)
                unsolved = search_problems(conn, "alice", "unsolved", None, None, None, None, 50, 0)
            finally:
                conn.close()
        self.assertEqual(len(solved), 1)
        self.assertEqual(solved[0]["problem_id"], "abc100_a")
        self.assertEqual(len(unsolved), 1)
        self.assertEqual(unsolved[0]["problem_id"], "abc100_b")

    def test_progress_summary(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
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
                            "problem_id": "abc100_a",
                            "contest_id": "abc100",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": 300,
                            "updated_epoch": 2,
                        },
                        {
                            "problem_id": "abc100_b",
                            "contest_id": "abc100",
                            "task_index": "B",
                            "title": "Beta",
                            "point": 200,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_b",
                            "difficulty": None,
                            "updated_epoch": 2,
                        },
                    ],
                )
                upsert_submissions(
                    conn,
                    [
                        {
                            "submission_id": 1,
                            "problem_id": "abc100_a",
                            "user_id": "alice",
                            "epoch_second": 100,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/1",
                        }
                    ],
                )
                conn.commit()
                summary = progress_summary(conn, "alice")
            finally:
                conn.close()
        bins = {item["bin"]: item for item in summary}
        self.assertEqual(bins["0-399"]["ac_count"], 1)
        self.assertEqual(bins["unknown"]["total_count"], 1)

    def test_recent_submissions(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
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
                            "problem_id": "abc100_a",
                            "contest_id": "abc100",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": 300,
                            "updated_epoch": 2,
                        }
                    ],
                )
                upsert_submissions(
                    conn,
                    [
                        {
                            "submission_id": 1,
                            "problem_id": "abc100_a",
                            "user_id": "alice",
                            "epoch_second": 100,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/1",
                        }
                    ],
                )
                conn.commit()
                items = recent_submissions(conn, "alice", 5)
            finally:
                conn.close()
        self.assertEqual(items[0]["problem_id"], "abc100_a")

    def test_contest_prefix_and_problems(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
                            "contest_id": "abc001",
                            "title": "ABC 1",
                            "start_epoch": 1,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        },
                        {
                            "contest_id": "abc002",
                            "title": "ABC 2",
                            "start_epoch": 2,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        },
                        {
                            "contest_id": "other001",
                            "title": "Other 1",
                            "start_epoch": 3,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "other",
                        },
                    ],
                )
                upsert_problems(
                    conn,
                    [
                        {
                            "problem_id": "abc001_a",
                            "contest_id": "abc001",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc001/tasks/abc001_a",
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                        {
                            "problem_id": "abc002_a",
                            "contest_id": "abc002",
                            "task_index": "A",
                            "title": "Beta",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc002/tasks/abc002_a",
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                    ],
                )
                conn.commit()
                contests = list_contests_by_prefix(conn, "abc", 10, 0)
                grouped = problems_by_contest(conn, "alice", contests)
                other = list_contests_other(conn, 10, 0)
                missing = list_contests_missing_tasks(conn, ["abc001", "abc002", "other001"])
            finally:
                conn.close()
        self.assertEqual(contests[0], "abc002")
        self.assertEqual(grouped["abc001"][0]["task_index"], "A")
        self.assertEqual(other[0], "other001")
        self.assertEqual(set(missing), {"other001"})

    def test_contests_missing_submissions(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(
                    conn,
                    [
                        {
                            "contest_id": "abc001",
                            "title": "ABC 1",
                            "start_epoch": 1,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        },
                        {
                            "contest_id": "abc002",
                            "title": "ABC 2",
                            "start_epoch": 2,
                            "duration_sec": 600,
                            "rated_range": "~1999",
                            "category": "abc",
                        },
                    ],
                )
                upsert_problems(
                    conn,
                    [
                        {
                            "problem_id": "abc001_a",
                            "contest_id": "abc001",
                            "task_index": "A",
                            "title": "Alpha",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc001/tasks/abc001_a",
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                        {
                            "problem_id": "abc002_a",
                            "contest_id": "abc002",
                            "task_index": "A",
                            "title": "Beta",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc002/tasks/abc002_a",
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                    ],
                )
                upsert_submissions(
                    conn,
                    [
                        {
                            "submission_id": 1,
                            "problem_id": "abc001_a",
                            "user_id": "alice",
                            "epoch_second": 100,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc001/submissions/1",
                        }
                    ],
                )
                conn.commit()
                missing = list_contests_missing_submissions(conn, "alice", ["abc001", "abc002"])
                ensure_sync_state(conn, "alice", "abc002")
                conn.commit()
                missing_after = list_contests_missing_submissions(conn, "alice", ["abc001", "abc002"])
            finally:
                conn.close()
        self.assertEqual(missing, ["abc002"])
        self.assertEqual(missing_after, [])
