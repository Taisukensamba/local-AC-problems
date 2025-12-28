import pathlib
import tempfile
import unittest
import sqlite3

from crawler.tasks import parse_tasks, crawl_tasks
from db.schema import init_db


class TasksParserTest(unittest.TestCase):
    def test_parse_tasks(self) -> None:
        html = pathlib.Path("data/fixtures/tasks_page.html").read_text(encoding="utf-8")
        tasks = parse_tasks(html, contest_id="abc100")
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["problem_id"], "abc100_a")
        self.assertEqual(tasks[0]["task_index"], "A")
        self.assertEqual(tasks[0]["point"], 100.0)

    def test_parse_tasks_ex_as_h(self) -> None:
        html = pathlib.Path("data/fixtures/tasks_page_ex.html").read_text(encoding="utf-8")
        tasks = parse_tasks(html, contest_id="abc233")
        self.assertEqual(tasks[0]["problem_id"], "abc233_h")
        self.assertEqual(tasks[0]["task_index"], "H")

    def test_parse_tasks_ex_from_title(self) -> None:
        html = pathlib.Path("data/fixtures/tasks_page_ex_title.html").read_text(encoding="utf-8")
        tasks = parse_tasks(html, contest_id="abc235")
        self.assertEqual(tasks[0]["problem_id"], "abc235_h")
        self.assertEqual(tasks[0]["task_index"], "H")

    def test_crawl_tasks(self) -> None:
        html = pathlib.Path("data/fixtures/tasks_page.html").read_text(encoding="utf-8")

        def fetch(_url: str) -> str:
            return html

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = sqlite3.connect(f.name)
            try:
                count = crawl_tasks(fetch, conn, "abc100")
                conn.commit()
                self.assertEqual(count, 2)
                row = conn.execute("SELECT COUNT(*) FROM problems").fetchone()
                self.assertEqual(row[0], 2)
            finally:
                conn.close()
