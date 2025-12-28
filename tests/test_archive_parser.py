import pathlib
import tempfile
import unittest

from crawler.archive import crawl_archive, find_next_page_url, parse_archive
from db.schema import init_db
from db.dao import upsert_contests
import sqlite3


class ArchiveParserTest(unittest.TestCase):
    def test_parse_archive(self) -> None:
        html = pathlib.Path("data/fixtures/archive_page1.html").read_text(encoding="utf-8")
        contests = parse_archive(html, category="abc")
        self.assertEqual(len(contests), 2)
        self.assertEqual(contests[0]["contest_id"], "abc100")
        self.assertEqual(contests[0]["category"], "abc")

    def test_find_next_page(self) -> None:
        html = pathlib.Path("data/fixtures/archive_page1.html").read_text(encoding="utf-8")
        next_url = find_next_page_url(html, "https://atcoder.jp/contests/archive")
        self.assertEqual(next_url, "https://atcoder.jp/contests/archive?page=2")

    def test_find_next_page_with_lang(self) -> None:
        html = pathlib.Path("data/fixtures/archive_page1.html").read_text(encoding="utf-8")
        next_url = find_next_page_url(html, "https://atcoder.jp/contests/archive?lang=ja")
        self.assertIn("lang=ja", next_url)
        self.assertIn("page=2", next_url)

    def test_crawl_archive_multiple_pages(self) -> None:
        pages = {
            "https://atcoder.jp/contests/archive": pathlib.Path(
                "data/fixtures/archive_page1.html"
            ).read_text(encoding="utf-8"),
            "https://atcoder.jp/contests/archive?page=2": pathlib.Path(
                "data/fixtures/archive_page2.html"
            ).read_text(encoding="utf-8"),
        }

        def fetch(url: str) -> str:
            return pages[url]

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = sqlite3.connect(f.name)
            try:
                total = crawl_archive(fetch, conn, "https://atcoder.jp/contests/archive", category="abc")
                conn.commit()
                self.assertEqual(total, 3)
                row = conn.execute("SELECT COUNT(*) FROM contests").fetchone()
                self.assertEqual(row[0], 3)
            finally:
                conn.close()

    def test_crawl_archive_idempotent(self) -> None:
        html = pathlib.Path("data/fixtures/archive_page2.html").read_text(encoding="utf-8")
        contests = parse_archive(html, category="abc")
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = sqlite3.connect(f.name)
            try:
                upsert_contests(conn, contests)
                upsert_contests(conn, contests)
                conn.commit()
                row = conn.execute("SELECT COUNT(*) FROM contests").fetchone()
                self.assertEqual(row[0], 1)
            finally:
                conn.close()
