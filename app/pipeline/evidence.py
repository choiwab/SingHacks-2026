"""Stable evidence identifiers and source-row records for computed facts."""

# Pandas' overloads widen common DataFrame selections into scalar and ndarray unions.
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any

import pandas as pd


def native(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def record(row: pd.Series, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: native(row[field]) for field in fields if field in row.index}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def evidence_id(table: str, row: pd.Series) -> str:
    if table == "holdings":
        key = f"{row['snapshot_date']}:{row['portfolio_id']}:{row['instrument_id']}"
    elif table == "event_log":
        canonical = json.dumps(
            record(
                row,
                (
                    "event_date",
                    "event_type",
                    "region",
                    "description",
                    "primary_transmission",
                    "severity",
                ),
            ),
            sort_keys=True,
            default=str,
        )
        key = f"{row['event_date']}:{sha256(canonical.encode()).hexdigest()[:16]}"
    elif table == "market_context":
        key = f"{row['snapshot_date']}:{row['series_id']}"
    elif table == "mandates":
        key = f"{row['mandate_code']}:{slug(str(row['asset_class']))}"
    else:
        id_field = next((field for field in row.index if field.endswith("_id")), None)
        canonical = json.dumps(record(row, tuple(sorted(row.index))), sort_keys=True, default=str)
        key = str(row[id_field]) if id_field else sha256(canonical.encode()).hexdigest()[:16]
    return f"{table}:{key}"


def add_evidence(
    evidence: dict[str, dict[str, Any]],
    table: str,
    row: pd.Series,
    title: str,
    fields: tuple[str, ...],
) -> str:
    identifier = evidence_id(table, row)
    evidence.setdefault(
        identifier,
        {
            "id": identifier,
            "kind": table.replace("_", " ").title(),
            "title": title,
            "source": f"data/{table}.csv",
            "record": record(row, fields),
        },
    )
    return identifier
