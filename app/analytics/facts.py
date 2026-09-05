"""Per-client fact formulas computed from validated source tables.

Moved verbatim from ``app/pipeline.py`` (ADR-0002). Member 4 owns every formula in this file.
"""

# Pandas' overloads widen common DataFrame selections into scalar and ndarray unions.
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from app.pipeline.evidence import add_evidence

AS_OF = date(2026, 8, 26)
SNAPSHOT = "2026-08-26"
BASELINE = "2025-12-31"

STOP_WORDS = {
    "and",
    "assets",
    "fund",
    "global",
    "linked",
    "market",
    "products",
    "the",
    "with",
}


def _fact(
    client_id: str,
    key: str,
    what: str,
    numbers: dict[str, Any],
    source_rows: list[str],
    event_ids: list[str] | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "id": f"{client_id}:fact:{key}",
        "what": what,
        "numbers": numbers,
        "source_rows": source_rows,
        "event_ids": event_ids or [],
        "confidence": confidence,
    }


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]{4,}", value.lower()) if token not in STOP_WORDS}


def _match_event(
    holding: pd.Series,
    events: pd.DataFrame,
    evidence: dict[str, dict[str, Any]],
) -> list[str]:
    haystack = " ".join(
        str(holding.get(field, ""))
        for field in ("instrument_name", "asset_class", "sub_asset_class", "sector", "region")
    )
    holding_tokens = _tokens(haystack)
    scored: list[tuple[int, pd.Series]] = []
    for _, event in events.iterrows():
        overlap = holding_tokens & _tokens(str(event["primary_transmission"]))
        if overlap:
            scored.append((len(overlap), event))
    if not scored:
        return []
    event = max(scored, key=lambda item: (item[0], str(item[1]["event_date"])))[1]
    return [
        add_evidence(
            evidence,
            "event_log",
            event,
            f"Event matched through {event['primary_transmission']}",
            ("event_date", "event_type", "region", "description", "primary_transmission"),
        )
    ]


def _mandate_fact(
    client: pd.Series,
    current: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    client_id = str(client["client_id"])
    portfolios = tables["portfolios"][tables["portfolios"]["client_id"] == client_id]
    mandate_codes = portfolios["mandate_code"].dropna().unique()
    bands = tables["mandates"][tables["mandates"]["mandate_code"].isin(mandate_codes)]
    total = current["market_value_base"].sum()
    weights = current.groupby("asset_class")["market_value_base"].sum().div(total).mul(100)
    candidates: list[tuple[float, str, float, float, str, pd.Series]] = []
    for _, band in bands.iterrows():
        actual = float(weights.get(band["asset_class"], 0))
        low, high = float(band["min_pct"]), float(band["max_pct"])
        below, above = low - actual, actual - high
        gap = max(below, above, 0)
        limit = low if below > above else high
        boundary = "minimum" if below > above else "maximum"
        candidates.append((gap, str(band["asset_class"]), actual, limit, boundary, band))
    default = (0, "None", 0, 0, "maximum", pd.Series())
    gap, asset_class, actual, limit, boundary, band = max(candidates, default=default)
    source_rows = [
        add_evidence(
            evidence,
            "holdings",
            row,
            "Current holding contributing to allocation denominator",
            (
                "snapshot_date",
                "portfolio_id",
                "instrument_id",
                "instrument_name",
                "asset_class",
                "market_value_base",
                "weight_pct",
                "valuation_date",
                "liquidity_tier",
                "portfolio_ccy",
                "sector",
            ),
        )
        for _, row in current.iterrows()
    ]
    if not band.empty:
        source_rows.append(
            add_evidence(
                evidence,
                "mandates",
                band,
                f"{band['mandate_name']} {asset_class} band",
                ("mandate_code", "mandate_name", "asset_class", "min_pct", "max_pct"),
            )
        )
    return _fact(
        str(client["client_id"]),
        "mandate-gap",
        f"{asset_class} is {actual:.1f}% against a {limit:.0f}% {boundary}.",
        {
            "asset_class": asset_class,
            "actual_pct": round(actual, 1),
            "limit_pct": round(limit, 1),
            "boundary": boundary,
            "gap_pct": round(gap, 1),
            "scope": "Household look-through; strictest applicable band",
        },
        source_rows,
    )


def _change_facts(
    client: pd.Series,
    holdings: pd.DataFrame,
    events: pd.DataFrame,
    evidence: dict[str, dict[str, Any]],
    as_of: date = AS_OF,
) -> list[dict[str, Any]]:
    client_id = str(client["client_id"])
    scoped_holdings = holdings[holdings["snapshot_date"] <= as_of.isoformat()]
    scoped_events = events[
        (events["event_date"] >= BASELINE) & (events["event_date"] <= as_of.isoformat())
    ]
    baseline = scoped_holdings[scoped_holdings["snapshot_date"] == BASELINE]
    current = scoped_holdings[scoped_holdings["snapshot_date"] == as_of.isoformat()]
    base_values = baseline.groupby("instrument_id")["market_value_base"].sum()
    current_values = current.groupby("instrument_id")["market_value_base"].sum()
    deltas = current_values.sub(base_values, fill_value=0).sort_values(key=abs, ascending=False)
    facts = []
    for index, (instrument_id, delta) in enumerate(deltas.head(3).items(), start=1):
        rows = scoped_holdings[scoped_holdings["instrument_id"] == instrument_id]
        representative = rows.sort_values("snapshot_date").iloc[-1]
        source_rows = [
            add_evidence(
                evidence,
                "holdings",
                row,
                f"{representative['instrument_name']} at {row['snapshot_date']}",
                (
                    "snapshot_date",
                    "portfolio_id",
                    "instrument_id",
                    "instrument_name",
                    "market_value_base",
                    "price_local",
                    "quantity",
                    "asset_class",
                    "sector",
                    "liquidity_tier",
                    "portfolio_ccy",
                    "weight_pct",
                    "valuation_date",
                ),
            )
            for _, row in rows[rows["snapshot_date"].isin([BASELINE, as_of.isoformat()])].iterrows()
        ]
        event_ids = _match_event(representative, scoped_events, evidence)
        facts.append(
            _fact(
                client_id,
                f"change-{index}",
                f"{representative['instrument_name']} position value changed by "
                f"{current['portfolio_ccy'].iloc[0]} {delta:,.0f} "
                f"between {BASELINE} and {as_of.isoformat()}.",
                {
                    "instrument": representative["instrument_name"],
                    "delta": round(float(delta), 2),
                    "currency": current["portfolio_ccy"].iloc[0],
                },
                source_rows,
                event_ids,
                "medium" if event_ids else "high",
            )
        )
    return facts


def _deadline_fact(
    client: pd.Series,
    current: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    evidence: dict[str, dict[str, Any]],
    as_of: date = AS_OF,
) -> dict[str, Any]:
    client_id = str(client["client_id"])
    needs = tables["planned_cash_needs"].query("client_id == @client_id")
    if needs.empty:
        due = date.fromisoformat(str(client["kyc_review_due"]))
        return _fact(
            client_id,
            "deadline",
            f"KYC review is due {due.strftime('%d %b %Y')}.",
            {"days": max((due - as_of).days, 0), "amount": 0, "currency": None},
            [
                add_evidence(
                    evidence,
                    "clients",
                    client,
                    str(client["client_name"]),
                    ("client_id", "client_name", "kyc_review_due"),
                )
            ],
        )
    need = needs.sort_values("due_from").iloc[0]
    due = date.fromisoformat(str(need["due_from"]))
    daily_holdings = current[current["liquidity_tier"] == "Daily"]
    daily = daily_holdings["market_value_base"].sum()
    daily_evidence = [
        add_evidence(
            evidence,
            "holdings",
            row,
            "Daily-liquid holding contributing to cash coverage",
            (
                "snapshot_date",
                "portfolio_id",
                "instrument_id",
                "market_value_base",
                "portfolio_ccy",
                "liquidity_tier",
            ),
        )
        for _, row in daily_holdings.iterrows()
    ]
    amount = float(need["amount"])
    portfolio_currency = str(current["portfolio_ccy"].iloc[0])
    amount_in_portfolio_currency, fx_evidence = _convert_currency(
        amount,
        str(need["currency"]),
        portfolio_currency,
        tables["market_context"],
        as_of,
        evidence,
    )
    evidence_id = add_evidence(
        evidence,
        "planned_cash_needs",
        need,
        str(need["description"]),
        ("need_id", "description", "currency", "amount", "due_from", "due_to", "certainty"),
    )
    return _fact(
        client_id,
        "deadline",
        f"{need['description']} of {need['currency']} {amount:,.0f} starts in "
        f"{max((due - as_of).days, 0)} days. Daily-liquid holdings total "
        f"{portfolio_currency} {daily:,.0f}, before collateral and other commitments.",
        {
            "days": max((due - as_of).days, 0),
            "amount": amount,
            "currency": need["currency"],
            "daily_liquid": round(float(daily), 2),
            "amount_in_portfolio_currency": round(amount_in_portfolio_currency, 2),
            "portfolio_currency": portfolio_currency,
            "coverage_pct": (
                round(min(daily / amount_in_portfolio_currency * 100, 999), 1)
                if amount_in_portfolio_currency
                else 999
            ),
            "description": need["description"],
        },
        [evidence_id, *fx_evidence, *daily_evidence],
    )


def _convert_currency(
    amount: float,
    source_currency: str,
    target_currency: str,
    market_context: pd.DataFrame,
    as_of: date,
    evidence: dict[str, dict[str, Any]],
) -> tuple[float, list[str]]:
    """Convert through USD using validated as-of quotes."""
    if source_currency == target_currency:
        return amount, []
    quote_rows = market_context[
        (market_context["snapshot_date"] == as_of.isoformat())
        & (market_context["category"] == "FX")
    ]
    quotes = quote_rows.set_index("series_id")["value"]
    citations: list[str] = []

    def quote(code: str) -> float:
        row = quote_rows[quote_rows["series_id"] == code].iloc[0]
        citations.append(
            add_evidence(
                evidence,
                "market_context",
                row,
                f"{code} exchange rate at {as_of.isoformat()}",
                ("snapshot_date", "series_id", "series_name", "unit", "value"),
            )
        )
        return float(quotes[code])

    def to_usd(value: float, currency: str) -> float:
        if currency == "USD":
            return value
        direct = f"{currency}USD"
        inverse = f"USD{currency}"
        if direct in quotes:
            return value * quote(direct)
        return value / quote(inverse)

    def from_usd(value: float, currency: str) -> float:
        if currency == "USD":
            return value
        direct = f"USD{currency}"
        inverse = f"{currency}USD"
        if direct in quotes:
            return value * quote(direct)
        return value / quote(inverse)

    converted = from_usd(to_usd(amount, source_currency), target_currency)
    return converted, list(dict.fromkeys(citations))


def _facility_fact(
    client_id: str,
    tables: dict[str, pd.DataFrame],
    evidence: dict[str, dict[str, Any]],
    as_of: date = AS_OF,
) -> dict[str, Any] | None:
    facilities = tables["credit_facilities"].query("client_id == @client_id")
    if facilities.empty:
        return None
    snapshots = [
        column.removeprefix("ltv_pct_")
        for column in facilities.columns
        if column.startswith("ltv_pct_")
        and date.fromisoformat(column.removeprefix("ltv_pct_")) <= as_of
    ]
    if not snapshots:
        raise ValueError(f"No facility LTV history at or before {as_of} for {client_id}")
    snapshot = max(snapshots)
    facility = facilities.sort_values(f"ltv_pct_{snapshot}", ascending=False).iloc[0]
    ltv = float(facility[f"ltv_pct_{snapshot}"])
    trigger = float(facility["margin_call_ltv_pct"])
    evidence_id = add_evidence(
        evidence,
        "credit_facilities",
        facility,
        f"Facility {facility['facility_id']} LTV history",
        (
            "facility_id",
            "facility_ccy",
            f"drawn_{snapshot}",
            f"lending_value_{snapshot}",
            f"ltv_pct_{snapshot}",
            "margin_call_ltv_pct",
        ),
    )
    return _fact(
        client_id,
        "facility",
        f"Facility LTV is {ltv:.2f}% against a {trigger:.2f}% trigger.",
        {"ltv_pct": ltv, "trigger_pct": trigger, "gap_pct": round(trigger - ltv, 2)},
        [evidence_id],
    )


def _theme_fact(
    client_id: str,
    current: pd.DataFrame,
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    keywords = {
        "CL-0014": ("property", "golden harbour", "mid-levels"),
        "CL-0019": ("shipping", "energy", "basket c"),
    }.get(client_id, ())
    if keywords:
        mask = current.apply(
            lambda row: any(
                keyword in " ".join(str(value).lower() for value in row.values)
                for keyword in keywords
            ),
            axis=1,
        )
        themed = current[mask]
    else:
        largest = current.sort_values("market_value_base", ascending=False).head(1)
        themed = largest
    total = current["market_value_base"].sum()
    value = themed["market_value_base"].sum()
    ids = [
        add_evidence(
            evidence,
            "holdings",
            row,
            "Current holding contributing to concentration denominator",
            (
                "snapshot_date",
                "instrument_id",
                "instrument_name",
                "sector",
                "market_value_base",
                "weight_pct",
                "liquidity_tier",
            ),
        )
        for _, row in current.iterrows()
    ]
    return _fact(
        client_id,
        "concentration",
        f"Connected positions represent {value / total * 100:.1f}% of the portfolio.",
        {"weight_pct": round(value / total * 100, 1), "value": round(float(value), 2)},
        ids,
    )


def _theme(row: pd.Series) -> str:
    fields = ("instrument_name", "sector", "sub_asset_class")
    text = " ".join(str(row.get(field, "")).lower() for field in fields)
    if "cash" in text or "deposit" in text:
        return "Cash"
    if any(word in text for word in ("shipping", "marine", "basket c")):
        return "Shipping"
    if any(word in text for word in ("energy", "oil", "gas")):
        return "Energy"
    if "gold" in text:
        return "Gold"
    if row["asset_class"] == "Fixed Income":
        return "Bonds"
    if row["asset_class"] == "Structured Products":
        return "Structured products"
    return "Other assets"


def _fact_engine(
    tables: dict[str, pd.DataFrame],
    as_of: date = AS_OF,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    evidence: dict[str, dict[str, Any]] = {}
    all_facts: dict[str, list[dict[str, Any]]] = {}
    holdings = tables["holdings"]
    for _, client in tables["clients"].iterrows():
        client_id = str(client["client_id"])
        client_holdings = holdings[holdings["client_id"] == client_id]
        current = client_holdings[client_holdings["snapshot_date"] == as_of.isoformat()]
        profile_id = add_evidence(
            evidence,
            "clients",
            client,
            str(client["client_name"]),
            (
                "client_id",
                "client_name",
                "country_of_residence",
                "booking_centre",
                "base_currency",
                "risk_profile",
                "objectives",
                "reporting_language",
                "risk_tolerance_score",
                "life_stage",
                "kyc_review_due",
            ),
        )
        profile = _fact(
            client_id,
            "profile",
            f"{client['client_name']} has a {client['risk_profile']} profile.",
            {
                "name": client["client_name"],
                "currency": current["portfolio_ccy"].iloc[0],
                "language": client["reporting_language"],
                "residence": client["country_of_residence"],
                "booking_centre": client["booking_centre"],
                "risk_tolerance_score": int(client["risk_tolerance_score"]),
                "life_stage": client["life_stage"],
            },
            [profile_id],
        )
        facts = [profile]
        facts.extend(_change_facts(client, client_holdings, tables["event_log"], evidence, as_of))
        facts.append(_mandate_fact(client, current, tables, evidence))
        facts.append(_deadline_fact(client, current, tables, evidence, as_of))
        facility = _facility_fact(client_id, tables, evidence, as_of)
        if facility:
            facts.append(facility)
        facts.append(_theme_fact(client_id, current, evidence))
        all_facts[client_id] = facts
    return all_facts, evidence


def fact_engine(
    tables: dict[str, pd.DataFrame],
    as_of: date = AS_OF,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Compute every fact for every client and the evidence those facts cite.

    Returns ``(facts, evidence)`` where ``facts`` maps client id to that client's fact list and
    ``evidence`` maps every cited evidence id to its source record.
    """
    return _fact_engine(tables, as_of)
