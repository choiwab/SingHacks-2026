"""Apply Controlled Updates in memory, retaining source identities and provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from app.pipeline.errors import SourceValidationError
from app.pipeline.evidence import evidence_id
from app.pipeline.stages.ingest import coerce_source_table

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "clients": ("client_id",),
    "portfolios": ("portfolio_id",),
    "instruments": ("instrument_id",),
    "mandates": ("mandate_code", "asset_class"),
    "transactions": ("transaction_id",),
    "credit_facilities": ("facility_id",),
    "commitments": ("commitment_id",),
    "planned_cash_needs": ("need_id",),
    "market_context": ("snapshot_date", "series_id"),
    "event_log": ("event_date", "description"),
    "rm_notes": ("note_id",),
    "holdings": ("snapshot_date", "portfolio_id", "instrument_id"),
}


@dataclass
class OverlayResult:
    tables: dict[str, pd.DataFrame]
    notes: list[dict[str, Any]]
    overlay_hashes: dict[str, str]
    overridden_keys: dict[str, list[str]]
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)


def row_key(table: str, row: dict[str, Any]) -> str:
    """Return the frozen upsert identity, independent of row ordering."""
    values = [row.get(field) for field in PRIMARY_KEYS[table]]
    if any(value is None or pd.isna(value) or str(value) == "" for value in values):
        raise ValueError(f"{table}: missing primary key")
    return ":".join(str(value) for value in values)


def _merge(table: str, base: list[dict[str, Any]], updates: list[dict[str, Any]]):
    keys = [row_key(table, row) for row in updates]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{table}: duplicate overlay key")
    replacements = dict(zip(keys, updates, strict=True))
    result = []
    for row in base:
        key = row_key(table, row)
        result.append(replacements.pop(key, dict(row)))
    result.extend(replacements.values())
    return result, sorted(keys)


def apply_overlay(
    tables: dict[str, pd.DataFrame],
    notes: list[dict[str, Any]],
    overlay_dir: Path | None,
) -> OverlayResult:
    """Upsert complete rows without touching any base files or caller-owned frames."""
    result = OverlayResult(
        {k: v.copy(deep=True) for k, v in tables.items()}, [dict(note) for note in notes], {}, {}
    )
    for table, frame in tables.items():
        for index, row in frame.iterrows():
            result.provenance[evidence_id(table, row)] = {
                "source_file": f"{table}.csv",
                "row_index": int(str(index)) + 2,
                "overridden": False,
            }
    for index, note in enumerate(notes, 1):
        result.provenance[f"rm_notes:{note['note_id']}"] = {
            "source_file": "rm_notes.json",
            "row_index": index,
            "overridden": False,
        }
    if overlay_dir is None:
        return result
    if not overlay_dir.is_dir():
        raise ValueError(f"Overlay directory does not exist: {overlay_dir}")
    for path in sorted(overlay_dir.iterdir()):
        if not path.is_file():
            continue
        table = path.stem
        if table not in PRIMARY_KEYS or path.suffix != (".json" if table == "rm_notes" else ".csv"):
            raise ValueError(f"Unsupported overlay source: {path.name}")
        raw = path.read_bytes()
        result.overlay_hashes[path.name] = sha256(raw).hexdigest()
        if table == "rm_notes":
            updates = json.loads(raw)
            if not isinstance(updates, list) or not all(isinstance(row, dict) for row in updates):
                raise ValueError("rm_notes.json: expected a list of objects")
            result.notes, keys = _merge(table, result.notes, updates)
        else:
            overlay = pd.read_csv(path, dtype=str, keep_default_na=False)
            if table not in result.tables:
                raise ValueError(f"{table}: base source missing")
            base = result.tables[table]
            if set(overlay.columns) != set(base.columns):
                raise ValueError(f"{path.name}: overlay must contain the complete source columns")
            overlay, diagnostics = coerce_source_table(table, overlay)
            if diagnostics:
                raise SourceValidationError(diagnostics)
            merged, keys = _merge(table, base.to_dict("records"), overlay.to_dict("records"))
            result.tables[table] = pd.DataFrame(merged, columns=base.columns).astype(
                base.dtypes.to_dict()
            )
            updates = overlay.to_dict("records")
        for index, row in enumerate(updates, 1 if table == "rm_notes" else 2):
            identifier = (
                f"rm_notes:{row['note_id']}"
                if table == "rm_notes"
                else evidence_id(table, pd.Series(row))
            )
            original = result.provenance.get(identifier)
            result.provenance[identifier] = {
                "source_file": f"fixtures/update/{path.name}",
                "source_path": str(path.resolve()),
                "row_index": index,
                "overridden": True,
                "original_row_index": original["row_index"] if original else None,
            }
        result.overridden_keys[path.name] = keys
    return result
