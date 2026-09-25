"""SQLite checkpoint so an interrupted crawl resumes without re-fetching finished work."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    source TEXT, window_start TEXT, window_end TEXT, page INTEGER,
    status TEXT, n_records INTEGER, total INTEGER, updated_at TEXT,
    PRIMARY KEY (source, window_start, window_end, page)
);
CREATE TABLE IF NOT EXISTS records (
    source TEXT, record_id TEXT, status TEXT, updated_at TEXT,
    PRIMARY KEY (source, record_id)
);
"""


class Checkpoint:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def page_done(self, source: str, start: str, end: str, page: int) -> bool:
        row = self.conn.execute(
            "SELECT status FROM pages WHERE source=? AND window_start=? AND window_end=? AND page=?",
            (source, start, end, page),
        ).fetchone()
        return row is not None and row[0] == "done"

    def mark_page(self, source: str, start: str, end: str, page: int, status: str,
                  n_records: int = 0, total: int | None = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?,?,?,?)",
            (source, start, end, page, status, n_records, total, self._now()),
        )
        self.conn.commit()

    def record_done(self, source: str, record_id: str) -> bool:
        row = self.conn.execute(
            "SELECT status FROM records WHERE source=? AND record_id=?", (source, record_id)
        ).fetchone()
        return row is not None and row[0] == "done"

    def mark_record(self, source: str, record_id: str, status: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?)",
                          (source, record_id, status, self._now()))
        self.conn.commit()

    def summary(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for source, status, n in self.conn.execute(
            "SELECT source, status, COUNT(*) FROM pages GROUP BY source, status"
        ):
            out.setdefault(source, {})[f"pages_{status}"] = n
        for source, status, n in self.conn.execute(
            "SELECT source, status, COUNT(*) FROM records GROUP BY source, status"
        ):
            out.setdefault(source, {})[f"records_{status}"] = n
        return out
