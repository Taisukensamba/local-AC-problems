import tempfile
import unittest

from db.dao import upsert_contests, upsert_problems, upsert_submissions
from db.schema import connect, init_db


class ProgressViewTest(unittest.TestCase):
    def test_progress_view_metrics(self) -> None:
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
                            "title": "Sample Problem",
                            "point": 100,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_a",
                            "difficulty": None,
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
                            "result": "WA",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/1",
                        },
                        {
                            "submission_id": 2,
                            "problem_id": "abc100_a",
                            "user_id": "alice",
                            "epoch_second": 120,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/2",
                        },
                    ],
                )
                conn.commit()
                row = conn.execute(
                    "SELECT is_ac, first_ac_epoch, last_submit_epoch, ac_count, wa_count "
                    "FROM progress WHERE problem_id = ? AND user_id = ?",
                    ("abc100_a", "alice"),
                ).fetchone()
            finally:
                conn.close()
        self.assertEqual(row, (1, 120, 120, 1, 1))
