import sqlite3
import tempfile
import unittest

from db.schema import init_db


class SchemaTest(unittest.TestCase):
    def test_init_db_creates_tables(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = sqlite3.connect(f.name)
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()
        self.assertIn("contests", tables)
        self.assertIn("problems", tables)
        self.assertIn("problem_tags", tables)
        self.assertIn("submissions", tables)
        self.assertIn("sync_state", tables)
