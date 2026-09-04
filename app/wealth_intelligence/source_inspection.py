"""Legacy read-only source inspection tools, owned by the data team."""

from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path

SOURCE_FILES = (
    "clients.csv",
    "portfolios.csv",
    "holdings.csv",
    "instruments.csv",
    "transactions.csv",
    "mandates.csv",
    "commitments.csv",
    "planned_cash_needs.csv",
    "credit_facilities.csv",
    "market_context.csv",
    "event_log.csv",
    "rm_notes.json",
)


def source_versions(source_dir: Path) -> tuple[dict[str, str], list[str]]:
    """Return content hashes and readable diagnostics for every expected source."""
    versions: dict[str, str] = {}
    issues: list[str] = []
    for name in SOURCE_FILES:
        path = source_dir / name
        try:
            versions[name] = sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            issues.append(f"{name}: {exc.strerror or 'unreadable'}")
    return versions, issues


def load_client_record(source_dir: Path, client_id: str) -> dict[str, str] | None:
    """Return one raw client row without mutating or normalizing source data."""
    try:
        with (source_dir / "clients.csv").open(encoding="utf-8", newline="") as source:
            return next(
                (row for row in csv.DictReader(source) if row.get("client_id") == client_id),
                None,
            )
    except OSError:
        return None
