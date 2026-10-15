"""SQLite persistence for processed IDs and run history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


def _timestamp(value: datetime) -> str:
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat(timespec="seconds")


class StateStore:
    """Transactional store. Publication precedes processed-ID marking in the agent."""

    def __init__(self, data_dir: str | Path, *, clock: Callable[[], datetime] | None = None) -> None:
        path = Path(data_dir)
        self.path = path if path.suffix == ".sqlite3" else path / "state.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS processed_articles (
                    article_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    report_path TEXT,
                    source_health TEXT NOT NULL,
                    error TEXT
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def is_processed(self, article_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM processed_articles WHERE article_id = ?", (article_id,)).fetchone() is not None

    def mark_processed(self, article_ids: Iterable[str], processed_at: datetime | None = None) -> None:
        stamp = _timestamp(processed_at or self.clock())
        with self._connect() as connection:
            connection.executemany("INSERT OR IGNORE INTO processed_articles(article_id, processed_at) VALUES (?, ?)", ((article_id, stamp) for article_id in article_ids))
            connection.commit()

    def record_run(self, run_id: str, *, started_at: datetime, finished_at: datetime | None, status: str, report_path: str | None = None, source_health: Any = None, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO runs
                (run_id, started_at, finished_at, status, report_path, source_health, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (run_id, _timestamp(started_at), _timestamp(finished_at) if finished_at else None, status, report_path, json.dumps(source_health or {}, sort_keys=True), error))
            connection.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


SQLiteState = StateStore
State = StateStore


class InMemoryState:
    """Fresh state for repeatable offline demos; never touches SQLite."""

    def __init__(self) -> None:
        self.processed: set[str] = set()
        self.runs: dict[str, dict[str, Any]] = {}

    def is_processed(self, article_id: str) -> bool:
        return article_id in self.processed

    def mark_processed(self, article_ids: Iterable[str], processed_at: datetime | None = None) -> None:
        self.processed.update(article_ids)

    def record_run(self, run_id: str, **values: Any) -> None:
        self.runs[run_id] = dict(values)
