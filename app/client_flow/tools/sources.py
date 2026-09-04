"""Read-only source inspection tools for the context agent.

Source hashing and the source file list are Member 3's (``app.pipeline.sources``) and are
re-exported here so the graph keeps one import path.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.pipeline.sources import SOURCE_FILES, source_versions

__all__ = ["SOURCE_FILES", "load_client_record", "source_versions"]


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
