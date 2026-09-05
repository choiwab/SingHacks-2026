"""As-of filtering and the Phase A normalization rules (EDA notebook section 12.3)."""

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

# Hand-curated issuer identity for single-name instruments (data dictionary:
# concentration_limit_applies="Y" marks single-name and single-asset exposures). The EDA
# notebook (section 12.2, instruments #5) requires this to be reviewed and version-controlled
# rather than parsed from free text at runtime.
ISSUER_BY_INSTRUMENT: dict[str, str] = {
    "SYN-ST-0101": "Bara Nusantara Energy",
    "SYN-ST-0102": "Meridian Semiconductor",
    "SYN-ST-0103": "Helios Cloud Systems",
    "SYN-ST-0104": "Pacific Orient Shipping",
    "SYN-ST-0105": "Sunrise Palm Resources",
    "SYN-ST-0106": "Golden Harbour Properties",
    "SYN-ST-0107": "Nordvind Industrial",
    "SYN-ST-0108": "Kanto Pharma Holdings",
    "SYN-ST-0109": "Verdant Health Group",
    "SYN-FI-0206": "Pacific Rim Bank",
    "SYN-FI-0207": "Golden Harbour Properties",
    "SYN-AL-0308": "Aranya Technologies",
}

# Hand-curated look-through of each structured product's `underlying_reference` (section 12.2,
# instruments #4). Full notional is attributed to every named leg that resolves to a qualifying
# single-name instrument ("attribution_basis": "worst_of_full_notional" per section 12.3 rule 4).
# Legs that do not resolve to a single-name instrument are kept with resolved=False and disclosed
# rather than guessed at (SYN-SP-0501 is a partial resolution, SYN-SP-0506 resolves nothing).
LOOKTHROUGH_BY_INSTRUMENT: dict[str, list[dict[str, Any]]] = {
    "SYN-SP-0501": [
        {"raw_name": "Global Energy Majors ADR", "issuer": None, "resolved": False},
        {"raw_name": "Gulf Marine Services", "issuer": None, "resolved": False},
        {"raw_name": "Helios Cloud Systems", "issuer": "Helios Cloud Systems", "resolved": True},
    ],
    "SYN-SP-0502": [
        {
            "raw_name": "Helios Cloud Systems Inc",
            "issuer": "Helios Cloud Systems",
            "resolved": True,
        },
    ],
    "SYN-SP-0503": [
        {
            "raw_name": "Golden Harbour Properties Ltd",
            "issuer": "Golden Harbour Properties",
            "resolved": True,
        },
    ],
    "SYN-SP-0504": [
        {"raw_name": "XAU spot", "issuer": None, "resolved": False},
    ],
    "SYN-SP-0505": [
        {
            "raw_name": "Pacific Orient Shipping",
            "issuer": "Pacific Orient Shipping",
            "resolved": True,
        },
        {"raw_name": "Global Energy Majors ADR", "issuer": None, "resolved": False},
        {"raw_name": "Bara Nusantara Energy", "issuer": "Bara Nusantara Energy", "resolved": True},
    ],
    "SYN-SP-0506": [
        {"raw_name": "three Asian banking majors", "issuer": None, "resolved": False},
    ],
}

_FX_CURRENCY_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("holdings", ("instrument_ccy", "portfolio_ccy")),
    ("clients", ("base_currency",)),
    ("portfolios", ("base_currency",)),
    ("planned_cash_needs", ("currency",)),
    ("commitments", ("currency",)),
    ("credit_facilities", ("facility_ccy",)),
)


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


def normalize_fx(tables: dict[str, pd.DataFrame], as_of: date) -> dict[str, pd.DataFrame]:
    """Publish a long ``fx_rates`` table: one USD conversion factor per snapshot and currency.

    Honors each series' market convention (data dictionary): a ``USDxxx`` quote is xxx per USD, so
    the USD factor is its reciprocal; an ``xxxUSD`` quote is already USD per xxx. This is an
    additive reference table only -- it never rewrites a column any curated-bundle schema expects,
    so downstream consumers that do not know about it are unaffected. See ``test_clean.py`` for the
    check against ``holdings.market_value_usd / market_value_local``, which validates the
    convention against every currency actually priced in this dataset.
    """
    market = tables["market_context"]
    fx = market[market["category"] == "FX"]
    quotes = {
        (str(row["snapshot_date"]), str(row["series_id"])): float(row["value"])
        for _, row in fx.iterrows()
    }
    currencies: set[str] = {"USD"}
    for table, fields in _FX_CURRENCY_FIELDS:
        frame = tables.get(table)
        if frame is None:
            continue
        for field in fields:
            if field in frame:
                currencies.update(str(value) for value in frame[field].dropna().unique())
    snapshots = sorted({str(value) for value in fx["snapshot_date"]})
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        for currency in sorted(currencies):
            if currency == "USD":
                rate = 1.0
            elif (snapshot, f"{currency}USD") in quotes:
                rate = quotes[(snapshot, f"{currency}USD")]
            elif (snapshot, f"USD{currency}") in quotes:
                rate = 1.0 / quotes[(snapshot, f"USD{currency}")]
            else:
                continue
            rows.append({"snapshot_date": snapshot, "currency": currency, "usd_per_unit": rate})
    fx_rates = pd.DataFrame(rows, columns=["snapshot_date", "currency", "usd_per_unit"])
    return {**tables, "fx_rates": fx_rates}


def normalize_bond_nominal(tables: dict[str, pd.DataFrame], as_of: date) -> dict[str, pd.DataFrame]:
    """Reconcile ``quantity * price_local`` against the reported ``market_value_local``.

    Bond quantities are already expressed in units of 100 nominal, so market value is
    ``quantity * price_local`` for every asset class without a further unit adjustment (data
    dictionary). Recomputing and comparing turns a silent unit change into a visible discrepancy
    instead of an accepted number; the result is published as an additive reconciliation table
    rather than mutating ``holdings``.
    """
    holdings = tables["holdings"]
    recomputed = holdings["quantity"].astype(float) * holdings["price_local"].astype(float)
    reported = holdings["market_value_local"].astype(float)
    discrepancy = (recomputed - reported).abs()
    tolerance = reported.abs() * 1e-6 + 1e-6
    reconciliation = holdings[
        ["snapshot_date", "portfolio_id", "instrument_id", "asset_class"]
    ].copy()
    reconciliation["recomputed_market_value_local"] = recomputed
    reconciliation["reported_market_value_local"] = reported
    reconciliation["discrepancy"] = discrepancy
    reconciliation["reconciled"] = discrepancy <= tolerance
    return {**tables, "holdings_reconciliation": reconciliation}


def look_through(tables: dict[str, pd.DataFrame], as_of: date) -> dict[str, pd.DataFrame]:
    """Publish the hand-curated issuer and structured-product look-through maps.

    Applied only for risk measures (concentration, event exposure), never for allocation against
    mandate bands (section 12.3 rule 4): a structured product still counts as Structured Products
    for the band test.
    """
    instruments = {str(value) for value in tables["instruments"]["instrument_id"]}
    issuer_map = pd.DataFrame(
        [
            {"instrument_id": instrument_id, "issuer": issuer}
            for instrument_id, issuer in ISSUER_BY_INSTRUMENT.items()
            if instrument_id in instruments
        ],
        columns=["instrument_id", "issuer"],
    )
    lookthrough_rows = [
        {
            "instrument_id": instrument_id,
            "raw_name": leg["raw_name"],
            "issuer": leg.get("issuer"),
            "resolved": leg["resolved"],
            "attribution_basis": "worst_of_full_notional",
        }
        for instrument_id, legs in LOOKTHROUGH_BY_INSTRUMENT.items()
        if instrument_id in instruments
        for leg in legs
    ]
    lookthrough_map = pd.DataFrame(
        lookthrough_rows,
        columns=["instrument_id", "raw_name", "issuer", "resolved", "attribution_basis"],
    )
    return {**tables, "issuer_map": issuer_map, "lookthrough_map": lookthrough_map}
