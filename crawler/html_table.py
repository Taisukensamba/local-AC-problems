from __future__ import annotations

from html.parser import HTMLParser


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cell_text: list[str] = []
        self._cell_links: list[str] = []
        self._current_row: list[dict] = []
        self.rows: list[list[dict]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table" and not self._in_table:
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_table and self._in_row and tag in ("td", "th"):
            self._in_cell = True
            self._cell_text = []
            self._cell_links = []
        elif self._in_cell and tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self._cell_links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if self._in_table and tag in ("td", "th") and self._in_cell:
            text = "".join(self._cell_text).strip()
            self._current_row.append({"text": text, "links": list(self._cell_links)})
            self._in_cell = False
        elif self._in_table and tag == "tr" and self._in_row:
            if self._current_row:
                self.rows.append(list(self._current_row))
            self._in_row = False
        elif self._in_table and tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)


def parse_first_table(html: str) -> list[list[dict]]:
    parser = TableParser()
    parser.feed(html)
    return parser.rows
