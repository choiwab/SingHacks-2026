"""Durable SQLite review ledger."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.wealth_intelligence.models import ReviewRecord, ReviewRequest


class ReviewLedger:
    """Append-only review persistence with a small, transactional interface."""

    def __init__(self, database: Path | str) -> None:
        database_text = str(database)
        self._anchor: sqlite3.Connection | None = None
        if database_text == ":memory:":
            self._database = f"file:monday-brief-{uuid4()}?mode=memory&cache=shared"
            self._uri = True
            self._anchor = self._connect()
        else:
            path = Path(database)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._database = str(path)
            self._uri = False
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database,
            uri=self._uri,
            timeout=5,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('Approve', 'Edit', 'Reject')),
                    reviewed_text TEXT NOT NULL,
                    rm TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS imports (
                    source TEXT PRIMARY KEY,
                    imported_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def append(self, request: ReviewRequest, *, rm: str) -> ReviewRecord:
        record = ReviewRecord(
            review_id=str(uuid4()),
            client_id=request.client_id,
            action=request.action,
            text=request.text,
            rm=rm,
            timestamp=datetime.now(UTC),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO reviews
                    (review_id, client_id, action, reviewed_text, rm, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.review_id,
                    record.client_id,
                    record.action,
                    record.text,
                    record.rm,
                    record.timestamp.isoformat(),
                ),
            )
            connection.commit()
        return record

    def list(self) -> list[ReviewRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT review_id, client_id, action, reviewed_text, rm, timestamp
                FROM reviews ORDER BY timestamp, review_id
                """
            ).fetchall()
        return [
            ReviewRecord(
                review_id=row["review_id"],
                client_id=row["client_id"],
                action=row["action"],
                text=row["reviewed_text"],
                rm=row["rm"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    def import_legacy_json(self, source: Path) -> int:
        """Import a legacy list once, leaving the source untouched."""
        if not source.exists():
            return 0
        source_key = str(source.resolve())
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot import legacy review log {source}: {exc}") from exc
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError(
                f"Cannot import legacy review log {source}: expected a list of objects"
            )

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            already_imported = connection.execute(
                "SELECT 1 FROM imports WHERE source = ?", (source_key,)
            ).fetchone()
            if already_imported:
                connection.rollback()
                return 0
            imported = 0
            for index, raw in enumerate(payload):
                record = self._legacy_record(raw, source_key, index)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO reviews
                        (review_id, client_id, action, reviewed_text, rm, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.review_id,
                        record.client_id,
                        record.action,
                        record.text,
                        record.rm,
                        record.timestamp.isoformat(),
                    ),
                )
                imported += connection.execute("SELECT changes()").fetchone()[0]
            connection.execute(
                "INSERT INTO imports (source, imported_at) VALUES (?, ?)",
                (source_key, datetime.now(UTC).isoformat()),
            )
            connection.commit()
        return imported

    @staticmethod
    def _legacy_record(raw: dict[str, Any], source: str, index: int) -> ReviewRecord:
        identity = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str)
        return ReviewRecord.model_validate(
            {
                "review_id": str(uuid5(NAMESPACE_URL, f"{source}:{index}:{identity}")),
                "client_id": raw.get("client_id"),
                "action": raw.get("action"),
                "text": raw.get("text", ""),
                "rm": raw.get("rm", "Priscilla Ong"),
                "timestamp": raw.get("timestamp"),
            }
        )

    def close(self) -> None:
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None
