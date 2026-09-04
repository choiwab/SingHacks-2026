"""Append-only SQLite persistence for pipeline runs, briefs, and RM reviews."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.pipeline.schemas import ReviewRecord, ReviewRequest


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    pipeline_version: str
    as_of: str
    source_hashes: dict[str, str]
    overlay_hashes: dict[str, str]
    is_seed: bool
    created_at: datetime
    status: str


@dataclass(frozen=True)
class BriefRecord:
    client_id: str
    run_id: str
    brief_version: int
    body: dict[str, Any]
    verification_report: dict[str, Any]
    origin: Literal["generated", "rm_edited"]
    created_at: datetime


class ReviewLedger:
    """Persist immutable versions; switching the active run never changes history."""

    def __init__(self, database: Path | str) -> None:
        self._anchor: sqlite3.Connection | None = None
        if str(database) == ":memory:":
            self._database = f"file:rm-intelligence-{uuid4()}?mode=memory&cache=shared"
            self._uri = True
            self._anchor = self._connect()
        else:
            path = Path(database)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._database = str(path)
            self._uri = False
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, uri=self._uri, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, pipeline_version TEXT NOT NULL,
                    as_of TEXT NOT NULL, source_hashes_json TEXT NOT NULL,
                    overlay_hashes_json TEXT NOT NULL, is_seed INTEGER NOT NULL,
                    created_at TEXT NOT NULL, status TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS briefs (
                    client_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(run_id),
                    brief_version INTEGER NOT NULL CHECK(brief_version > 0),
                    body_json TEXT NOT NULL, verification_report_json TEXT NOT NULL,
                    origin TEXT NOT NULL CHECK(origin IN ('generated', 'rm_edited')),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(client_id, run_id, brief_version)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('Approve', 'Edit', 'Reject')),
                    reviewed_text TEXT NOT NULL, rm TEXT NOT NULL, timestamp TEXT NOT NULL
                )
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(reviews)")}
            for name, kind in (
                ("run_id", "TEXT"),
                ("brief_version", "INTEGER"),
                ("section", "TEXT"),
                ("reason", "TEXT"),
                ("verification_report_id", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE reviews ADD COLUMN {name} {kind}")
            connection.execute("""
                CREATE INDEX IF NOT EXISTS reviews_run_client
                ON reviews(run_id, client_id, brief_version)
            """)
            connection.commit()

    def add_run(
        self,
        *,
        run_id: str,
        pipeline_version: str,
        as_of: date | str,
        source_hashes: dict[str, str],
        overlay_hashes: dict[str, str] | None = None,
        is_seed: bool = False,
        status: str = "ready",
    ) -> RunRecord:
        """Register once; identical retries succeed and conflicting identities fail."""
        values = (
            run_id,
            pipeline_version,
            str(as_of),
            json.dumps(source_hashes, sort_keys=True),
            json.dumps(overlay_hashes or {}, sort_keys=True),
            int(is_seed),
            status,
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing:
                previous = tuple(
                    existing[key]
                    for key in (
                        "run_id",
                        "pipeline_version",
                        "as_of",
                        "source_hashes_json",
                        "overlay_hashes_json",
                        "is_seed",
                        "status",
                    )
                )
                if previous != values:
                    raise ValueError(f"Run {run_id} already exists with different metadata")
                return self._run(existing)
            connection.execute(
                """
                INSERT INTO runs (run_id, pipeline_version, as_of, source_hashes_json,
                    overlay_hashes_json, is_seed, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (*values, datetime.now(UTC).isoformat()),
            )
            connection.commit()
        record = self.get_run(run_id)
        assert record is not None
        return record

    @staticmethod
    def _run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            pipeline_version=row["pipeline_version"],
            as_of=row["as_of"],
            source_hashes=json.loads(row["source_hashes_json"]),
            overlay_hashes=json.loads(row["overlay_hashes_json"]),
            is_seed=bool(row["is_seed"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
        )

    def get_run(self, run_id: str) -> RunRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._run(row) if row else None

    def list_runs(self) -> list[RunRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM runs ORDER BY created_at, run_id").fetchall()
        return [self._run(row) for row in rows]

    def seed_run(self) -> RunRecord | None:
        """Return the original seed, even after subsequent seed rebuilds or updates."""
        return next((run for run in self.list_runs() if run.is_seed), None)

    def store_brief(
        self,
        *,
        client_id: str,
        run_id: str,
        body: dict[str, Any],
        verification_report: dict[str, Any],
        origin: Literal["generated", "rm_edited"] = "generated",
        brief_version: int | None = None,
    ) -> BriefRecord:
        """Append the next version, allocating its number under the write lock."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute(
                "SELECT COALESCE(MAX(brief_version), 0) FROM briefs WHERE client_id=? AND run_id=?",
                (client_id, run_id),
            ).fetchone()[0]
            version = latest + 1
            if brief_version is not None and brief_version != version:
                raise ValueError(f"Expected brief version {version}, got {brief_version}")
            created_at = datetime.now(UTC)
            connection.execute(
                """
                INSERT INTO briefs (client_id, run_id, brief_version, body_json,
                    verification_report_json, origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    client_id,
                    run_id,
                    version,
                    json.dumps(body),
                    json.dumps(verification_report),
                    origin,
                    created_at.isoformat(),
                ),
            )
            connection.commit()
        return BriefRecord(
            client_id, run_id, version, body, verification_report, origin, created_at
        )

    @staticmethod
    def _brief(row: sqlite3.Row) -> BriefRecord:
        return BriefRecord(
            client_id=row["client_id"],
            run_id=row["run_id"],
            brief_version=row["brief_version"],
            body=json.loads(row["body_json"]),
            verification_report=json.loads(row["verification_report_json"]),
            origin=row["origin"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_brief(
        self,
        client_id: str,
        run_id: str,
        brief_version: int | None = None,
    ) -> BriefRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM briefs WHERE client_id=? AND run_id=?
                    AND (? IS NULL OR brief_version=?) ORDER BY brief_version DESC LIMIT 1
            """,
                (client_id, run_id, brief_version, brief_version),
            ).fetchone()
        return self._brief(row) if row else None

    def list_briefs(self, run_id: str, client_id: str | None = None) -> list[BriefRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM briefs WHERE run_id=? AND (? IS NULL OR client_id=?)
                ORDER BY client_id, brief_version
            """,
                (run_id, client_id, client_id),
            ).fetchall()
        return [self._brief(row) for row in rows]

    def append(
        self,
        request: ReviewRequest,
        *,
        rm: str,
        verification_report_id: str | None = None,
    ) -> ReviewRecord:
        data = request.model_dump()
        data.update(review_id=str(uuid4()), rm=rm, timestamp=datetime.now(UTC))
        if "verification_report_id" in ReviewRecord.model_fields:
            data["verification_report_id"] = verification_report_id
        record = ReviewRecord.model_validate(data)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            run_id, version = data.get("run_id"), data.get("brief_version")
            if (run_id is None) != (version is None):
                raise ValueError("Review run_id and brief_version must be supplied together")
            if (
                run_id is not None
                and not connection.execute(
                    "SELECT 1 FROM briefs WHERE client_id=? AND run_id=? AND brief_version=?",
                    (request.client_id, run_id, version),
                ).fetchone()
            ):
                raise ValueError("Review references an unknown brief version")
            connection.execute(
                """
                INSERT INTO reviews (review_id, client_id, action, reviewed_text, rm, timestamp,
                    run_id, brief_version, section, reason, verification_report_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.review_id,
                    record.client_id,
                    record.action,
                    record.text or "",
                    rm,
                    record.timestamp.isoformat(),
                    run_id,
                    version,
                    data.get("section"),
                    data.get("reason"),
                    verification_report_id,
                ),
            )
            connection.commit()
        return record

    def list(
        self,
        run_id: str | None = None,
        *,
        client_id: str | None = None,
        brief_version: int | None = None,
    ) -> list[ReviewRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM reviews WHERE (? IS NULL OR run_id=?)
                    AND (? IS NULL OR client_id=?) AND (? IS NULL OR brief_version=?)
                ORDER BY timestamp, review_id
            """,
                (run_id, run_id, client_id, client_id, brief_version, brief_version),
            ).fetchall()
        records = []
        for row in rows:
            data = dict(row)
            data["text"] = data.pop("reviewed_text")
            records.append(
                ReviewRecord.model_validate(
                    {key: value for key, value in data.items() if key in ReviewRecord.model_fields}
                )
            )
        return records

    def close(self) -> None:
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None
