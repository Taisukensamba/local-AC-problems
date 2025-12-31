import tempfile
import unittest

from db.dao import upsert_contests, upsert_problems, upsert_submissions
from db.schema import connect, init_db
from oj.atcoder import atcoder_oj


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
                upsert_submissions(
                    conn,
                    [
                        {
                            "submission_uid": atcoder_oj.submission_uid(1),
                            "oj": atcoder_oj.name,
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                            ),
                            "user_id": "alice",
                            "epoch_second": 100,
                            "result": "WA",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/1",
                        },
                        {
                            "submission_uid": atcoder_oj.submission_uid(2),
                            "oj": atcoder_oj.name,
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                            ),
                            "user_id": "alice",
                            "epoch_second": 120,
                            "result": "AC",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/2",
                        },
                        {
                            "submission_uid": atcoder_oj.submission_uid(3),
                            "oj": atcoder_oj.name,
                            "problem_uid": atcoder_oj.problem_uid(
                                contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                            ),
                            "user_id": "alice",
                            "epoch_second": 130,
                            "result": "TLE",
                            "language": "Python",
                            "exec_ms": 10,
                            "memory_kib": 512,
                            "url": "https://atcoder.jp/contests/abc100/submissions/3",
                        },
                    ],
                )
                conn.commit()
                row = conn.execute(
                    "SELECT is_ac, first_ac_epoch, last_submit_epoch, ac_count, not_ac_count "
                    "FROM progress WHERE problem_uid = ? AND user_id = ?",
                    (
                        atcoder_oj.problem_uid(
                            contest_id="abc100", index="A", name=None, problem_id="abc100_a"
                        ),
                        "alice",
                    ),
                ).fetchone()
            finally:
                conn.close()
        self.assertEqual(row, (1, 120, 130, 1, 2))
