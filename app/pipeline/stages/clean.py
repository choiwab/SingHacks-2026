"""As-of filtering and the explicit boundary for Member 4 normalization rules."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import pandas as pd

# Dates describing future obligations are retained. Observation dates are filtered.
OBSERVATION_DATES = {
    "holdings": ("snapshot_date", "valuation_date", "acquired_date"),
    "transactions": ("trade_date", "settlement_date"),
    "event_log": ("event_date",),
    "market_context": ("snapshot_date",),
    "portfolios": ("inception_date",),
    "clients": ("client_since",),
}
NormalizationRule = Callable[[dict[str, pd.DataFrame], date], dict[str, pd.DataFrame]]


@dataclass
class CleanedSources:
    tables: dict[str, pd.DataFrame]
    notes: list[dict[str, Any]]
    clients: dict[str, dict[str, pd.DataFrame]]
    as_of: date


def clean_sources(
    tables: dict[str, pd.DataFrame],
    notes: list[dict[str, Any]],
    *,
    as_of: date,
    normalize_fx: NormalizationRule | None = None,
    normalize_bond_nominal: NormalizationRule | None = None,
    look_through: NormalizationRule | None = None,
) -> CleanedSources:
    """Filter before invoking analytics hooks; never mutate the ingested Source Records."""
    cleaned: dict[str, pd.DataFrame] = {}
    cutoff = as_of.isoformat()
    observations = cast(
        pd.Series, tables.get("holdings", pd.DataFrame()).get("snapshot_date", pd.Series(dtype=str))
    )
    latest = str(observations.max()) if not observations.empty else cutoff
    for name, source in tables.items():
        frame = source.copy(deep=True)
        for field in OBSERVATION_DATES.get(name, ()):
            if field in frame:
                frame = cast(
                    pd.DataFrame, frame[frame[field].isna() | (frame[field].astype(str) <= cutoff)]
                )
        columns = []
        for field in frame.columns:
            dated = re.search(r"(\d{4}-\d{2}-\d{2})$", str(field))
            if (
                dated
                and dated[1] > cutoff
                or cutoff < latest
                and (field.endswith("_current") or field == "total_aum_usd")
            ):
                columns.append(field)
        cleaned[name] = frame.drop(columns=columns)
    clean_notes = [dict(note) for note in notes if str(note["note_date"]) <= cutoff]
    for normalize in (normalize_fx, normalize_bond_nominal, look_through):
        if normalize is not None:
            cleaned = normalize(cleaned, as_of)
    client_ids = cleaned["clients"]["client_id"].astype(str)
    clients = {
        client_id: {
            name: cast(pd.DataFrame, frame[frame["client_id"] == client_id]).copy()
            if "client_id" in frame
            else frame.copy()
            for name, frame in cleaned.items()
        }
        for client_id in client_ids
    }
    return CleanedSources(cleaned, clean_notes, clients, as_of)
