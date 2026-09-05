"""Durable, client-scoped Connected Records and idempotent Review Decisions."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agents.contracts import ReviewAction, fingerprint
from app.mcp.records import SOURCES, CommunicationRecord, ConnectedContext
from app.mcp.retrieval import record_content


def _validate_client(client_id: str) -> None:
    if not re.fullmatch(r"CL-\d{4}", client_id):
        raise ValueError("Expected a scoped client ID such as CL-0003")


class MemoryStore:
    """Append-only versions, with a fresh, closed SQLite connection per operation.

    Context uses the latest inserted eligible version, not historical knowledge at
    ingestion time. Corrections preserve earlier versions for audit through history().
    This is a local single-RM demo store, not an authorization boundary.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        if str(self.path) == ":memory:":
            raise ValueError("Persistent memory requires a file path")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.touch(mode=0o600, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS memory_records (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE (client_id, record_id, version)
                );
                CREATE INDEX IF NOT EXISTS memory_record_owner
                    ON memory_records (record_id);
                CREATE TABLE IF NOT EXISTS memory_reviews (
                    event_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS connector_snapshots (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def put(self, record: CommunicationRecord) -> None:
        # Revalidate because Pydantic model_copy can bypass boundary validation.
        record = CommunicationRecord.model_validate(record.model_dump())
        _validate_client(record.client_id)
        if not record.version.strip():
            raise ValueError("Record version must not be empty")
        cached = record.model_copy(update={"availability": "Cached"})
        content_hash = fingerprint(record_content(cached))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT client_id FROM memory_records WHERE record_id = ? LIMIT 1",
                (record.id,),
            ).fetchone()
            if owner and owner[0] != record.client_id:
                raise ValueError("Record ID already belongs to a different client")
            existing = connection.execute(
                """SELECT content_hash FROM memory_records
                   WHERE client_id = ? AND record_id = ? AND version = ?""",
                (record.client_id, record.id, record.version),
            ).fetchone()
            if existing:
                if existing[0] != content_hash:
                    raise ValueError("Conflicting content for an existing record version")
                return
            connection.execute(
                """INSERT INTO memory_records
                   (client_id, record_id, version, content_hash, payload) VALUES (?, ?, ?, ?, ?)""",
                (
                    record.client_id,
                    record.id,
                    record.version,
                    content_hash,
                    cached.model_dump_json(),
                ),
            )

    def context(
        self, client_id: str, as_of: datetime, revision: str = "current"
    ) -> ConnectedContext:
        """Return the latest eligible versions; revision is a loader-compatible hint."""
        _validate_client(client_id)
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Persistent memory requires an aware as-of timestamp")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM memory_records WHERE client_id = ? ORDER BY sequence",
                (client_id,),
            ).fetchall()
            snapshots = connection.execute(
                "SELECT as_of, payload FROM connector_snapshots "
                "WHERE client_id = ? ORDER BY sequence",
                (client_id,),
            ).fetchall()
        # ponytail: scan one client's versions; SQL date indexing if the demo outgrows this.
        latest: dict[str, CommunicationRecord] = {}
        for (payload,) in rows:
            record = CommunicationRecord.model_validate_json(payload)
            if record.occurred_at <= as_of:
                latest[record.id] = record
        # Snapshot membership excludes disappeared external records from current recall.
        # Immutable versions remain available through the local history command.
        eligible_snapshots = []
        managed_ids = set()
        for cutoff, payload in snapshots:
            snapshot = ConnectedContext.model_validate_json(payload)
            managed_ids.update(r.id for r in snapshot.records)
            if datetime.fromisoformat(cutoff) <= as_of:
                eligible_snapshots.append((datetime.fromisoformat(cutoff), snapshot))
        latest = {key: value for key, value in latest.items() if key not in managed_ids}
        snapshot_log = []
        snapshot_sources = {}
        if eligible_snapshots:
            snapshot = sorted(eligible_snapshots, key=lambda item: item[0])[-1][1]
            latest.update({r.id: r for r in snapshot.records if r.occurred_at <= as_of})
            snapshot_log = snapshot.retrieval_log
            snapshot_sources = snapshot.sources
        records = sorted(latest.values(), key=lambda record: (record.occurred_at, record.id))
        return ConnectedContext(
            records=records,
            sources={
                source: "Cached"
                if any(r.source == source for r in records)
                or snapshot_sources.get(source) == "Cached"
                else "Not connected"
                for source in dict.fromkeys(
                    [*SOURCES, *snapshot_sources, *[r.source for r in records]]
                )
            },
            retrieval_log=[
                {
                    "mode": "persistent_memory",
                    "client_id": client_id,
                    "as_of": as_of.isoformat(),
                    "record_ids": [record.id for record in records],
                },
                *snapshot_log,
            ],
        )

    def save_connector_snapshot(
        self, client_id: str, as_of: datetime, context: ConnectedContext
    ) -> None:
        """Publish a complete successful read; failed/partial reads must not call this."""
        _validate_client(client_id)
        context = ConnectedContext.model_validate(context.model_dump())
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Connector snapshot requires an aware As-of Date")
        if any(
            r.client_id != client_id or r.occurred_at > as_of or r.provenance != "recorded_live"
            for r in context.records
        ):
            raise ValueError("Invalid connector snapshot scope or provenance")
        cached = ConnectedContext(
            records=[r.model_copy(update={"availability": "Cached"}) for r in context.records],
            sources={
                source: "Cached" if status == "Live" else status
                for source, status in context.sources.items()
            },
            retrieval_log=[
                {**entry, "mode": "connector_snapshot_replay"} for entry in context.retrieval_log
            ],
        )
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for record in cached.records:
                content_hash = fingerprint(record_content(record))
                owner = connection.execute(
                    "SELECT client_id FROM memory_records WHERE record_id = ? LIMIT 1", (record.id,)
                ).fetchone()
                if owner and owner[0] != client_id:
                    raise ValueError("Record belongs to a different Client")
                prior = connection.execute(
                    "SELECT content_hash FROM memory_records "
                    "WHERE client_id = ? AND record_id = ? AND version = ?",
                    (client_id, record.id, record.version),
                ).fetchone()
                if prior and prior[0] != content_hash:
                    raise ValueError("Conflicting connector record version")
                connection.execute(
                    "INSERT OR IGNORE INTO memory_records "
                    "(client_id, record_id, version, content_hash, payload) VALUES (?, ?, ?, ?, ?)",
                    (client_id, record.id, record.version, content_hash, record.model_dump_json()),
                )
            connection.execute(
                "INSERT INTO connector_snapshots (client_id, as_of, payload) VALUES (?, ?, ?)",
                (client_id, as_of.isoformat(), cached.model_dump_json()),
            )

    def history(self, client_id: str, record_id: str) -> list[CommunicationRecord]:
        """Local audit history, including future-dated records, never an as-of retrieval."""
        _validate_client(client_id)
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT payload FROM memory_records
                   WHERE client_id = ? AND record_id = ? ORDER BY sequence""",
                (client_id, record_id),
            ).fetchall()
        return [CommunicationRecord.model_validate_json(payload) for (payload,) in rows]

    def record_review(self, event: dict[str, Any]) -> None:
        """Checkpoint retries never duplicate or rewrite a Review Decision."""
        action = ReviewAction.model_validate(
            {key: value for key, value in event.items() if key != "event_id"}
        )
        _validate_client(action.client_id)
        normalized = action.model_dump(mode="json")
        if event.get("event_id") != fingerprint(normalized):
            raise ValueError("Review event ID must match its content")
        payload = json.dumps({"event_id": event["event_id"], **normalized}, sort_keys=True)
        with self._connection() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO memory_reviews (event_id, client_id, payload)
                   VALUES (?, ?, ?)""",
                (event["event_id"], action.client_id, payload),
            )
