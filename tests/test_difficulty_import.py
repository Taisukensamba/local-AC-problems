import pathlib
import tempfile
import unittest

from crawler.difficulty_import import import_difficulty, parse_problem_models
from db.dao import upsert_contests, upsert_problems
from db.schema import connect, init_db


class DifficultyImportTest(unittest.TestCase):
    def test_parse_problem_models(self) -> None:
        payload = pathlib.Path("data/fixtures/problem-models.json").read_text(encoding="utf-8")
        items = parse_problem_models(payload)
        self.assertEqual(items[0]["problem_id"], "abc100_a")
        self.assertEqual(items[0]["difficulty"], 100)

    def test_import_difficulty(self) -> None:
        payload = pathlib.Path("data/fixtures/problem-models.json").read_text(encoding="utf-8")

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
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                        {
                            "problem_id": "abc100_b",
                            "contest_id": "abc100",
                            "task_index": "B",
                            "title": "Beta",
                            "point": 200,
                            "url": "https://atcoder.jp/contests/abc100/tasks/abc100_b",
                            "difficulty": None,
                            "updated_epoch": None,
                        },
                    ],
                )
                count = import_difficulty(fetch, conn, "https://example.com/problem-models.json")
                conn.commit()
                self.assertEqual(count, 2)
                rows = conn.execute(
                    "SELECT problem_id, difficulty FROM problems ORDER BY problem_id"
                ).fetchall()
                self.assertEqual(rows[0], ("abc100_a", 100))
                self.assertEqual(rows[1], ("abc100_b", 300))
            finally:
                conn.close()
