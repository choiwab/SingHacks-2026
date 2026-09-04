"""Offline fact-to-narrative pipeline for the Monday Brief demo."""

# Pandas' overloads widen common DataFrame selections into scalar and ndarray unions.
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

from __future__ import annotations

import json
import re
from datetime import date
from hashlib import sha256
from typing import Any

import pandas as pd

from app.monday_brief.policy import POLICY

AS_OF = date(2026, 8, 26)
SNAPSHOT = "2026-08-26"
BASELINE = "2025-12-31"

TABLE_NAMES = (
    "clients",
    "credit_facilities",
    "event_log",
    "holdings",
    "mandates",
    "market_context",
    "planned_cash_needs",
    "portfolios",
)

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


def _native(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _record(row: pd.Series, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _native(row[field]) for field in fields if field in row.index}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _evidence_id(table: str, row: pd.Series) -> str:
    if table == "holdings":
        key = f"{row['snapshot_date']}:{row['portfolio_id']}:{row['instrument_id']}"
    elif table == "event_log":
        canonical = json.dumps(
            _record(
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
        key = f"{row['mandate_code']}:{_slug(str(row['asset_class']))}"
    else:
        id_field = next((field for field in row.index if field.endswith("_id")), None)
        canonical = json.dumps(_record(row, tuple(sorted(row.index))), sort_keys=True, default=str)
        key = str(row[id_field]) if id_field else sha256(canonical.encode()).hexdigest()[:16]
    return f"{table}:{key}"


def _add_evidence(
    evidence: dict[str, dict[str, Any]],
    table: str,
    row: pd.Series,
    title: str,
    fields: tuple[str, ...],
) -> str:
    evidence_id = _evidence_id(table, row)
    evidence.setdefault(
        evidence_id,
        {
            "id": evidence_id,
            "kind": table.replace("_", " ").title(),
            "title": title,
            "source": f"data/{table}.csv",
            "record": _record(row, fields),
        },
    )
    return evidence_id


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
        _add_evidence(
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
    rows = current[current["asset_class"] == asset_class]
    source_rows = [
        _add_evidence(
            evidence,
            "holdings",
            row,
            f"Current {asset_class} holding",
            (
                "snapshot_date",
                "portfolio_id",
                "instrument_id",
                "instrument_name",
                "asset_class",
                "market_value_base",
                "weight_pct",
            ),
        )
        for _, row in rows.iterrows()
    ]
    if not band.empty:
        source_rows.append(
            _add_evidence(
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
    baseline = holdings[holdings["snapshot_date"] == BASELINE]
    current = holdings[holdings["snapshot_date"] == as_of.isoformat()]
    base_values = baseline.groupby("instrument_id")["market_value_base"].sum()
    current_values = current.groupby("instrument_id")["market_value_base"].sum()
    deltas = current_values.sub(base_values, fill_value=0).sort_values(key=abs, ascending=False)
    facts = []
    for index, (instrument_id, delta) in enumerate(deltas.head(3).items(), start=1):
        rows = holdings[holdings["instrument_id"] == instrument_id]
        representative = rows.sort_values("snapshot_date").iloc[-1]
        source_rows = [
            _add_evidence(
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
                ),
            )
            for _, row in rows[rows["snapshot_date"].isin([BASELINE, SNAPSHOT])].iterrows()
        ]
        event_ids = _match_event(representative, events, evidence)
        facts.append(
            _fact(
                client_id,
                f"change-{index}",
                f"{representative['instrument_name']} changed by {delta:,.0f}.",
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
            [],
        )
    need = needs.sort_values("due_from").iloc[0]
    due = date.fromisoformat(str(need["due_from"]))
    daily = current[current["liquidity_tier"] == "Daily"]["market_value_base"].sum()
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
    evidence_id = _add_evidence(
        evidence,
        "planned_cash_needs",
        need,
        str(need["description"]),
        ("need_id", "description", "currency", "amount", "due_from", "due_to", "certainty"),
    )
    return _fact(
        client_id,
        "deadline",
        f"{need['description']} starts in {max((due - as_of).days, 0)} days.",
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
        [evidence_id, *fx_evidence],
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
            _add_evidence(
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
) -> dict[str, Any] | None:
    facilities = tables["credit_facilities"].query("client_id == @client_id")
    if facilities.empty:
        return None
    facility = facilities.sort_values("ltv_pct_2026-08-26", ascending=False).iloc[0]
    ltv = float(facility["ltv_pct_2026-08-26"])
    trigger = float(facility["margin_call_ltv_pct"])
    evidence_id = _add_evidence(
        evidence,
        "credit_facilities",
        facility,
        f"Facility {facility['facility_id']} LTV history",
        (
            "facility_id",
            "facility_ccy",
            "drawn_2026-08-26",
            "lending_value_2026-08-26",
            "ltv_pct_2026-08-26",
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
        _add_evidence(
            evidence,
            "holdings",
            row,
            "Current concentration holding",
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
        for _, row in themed.iterrows()
    ]
    return _fact(
        client_id,
        "concentration",
        f"Connected positions represent {value / total * 100:.1f}% of the portfolio.",
        {"weight_pct": round(value / total * 100, 1), "value": round(float(value), 2)},
        ids,
    )


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
        profile_id = _add_evidence(
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
        facility = _facility_fact(client_id, tables, evidence)
        if facility:
            facts.append(facility)
        facts.append(_theme_fact(client_id, current, evidence))
        all_facts[client_id] = facts
    return all_facts, evidence


def _belief_extractor(
    notes: list[dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_client: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        evidence_id = f"rm_notes:{note['note_id']}"
        evidence[evidence_id] = {
            "id": evidence_id,
            "kind": "RM note",
            "title": f"{note['channel']} on {note['note_date']}",
            "source": "data/rm_notes.json",
            "record": note,
        }
        by_client.setdefault(note["client_id"], []).append(note)
    beliefs: dict[str, list[dict[str, Any]]] = {}
    for client_id, client_notes in by_client.items():
        known = POLICY.known_beliefs.get(client_id)
        if known:
            beliefs[client_id] = [
                {
                    "id": f"{client_id}:belief:1",
                    "text": known.text,
                    "note_id": known.note_id,
                    "citations": [f"rm_notes:{known.note_id}"],
                }
            ]
            continue
        latest = max(client_notes, key=lambda item: item["note_date"])
        sentences = re.split(r"(?<=[.!?])\s+", latest["note"])
        belief = next(
            (
                sentence
                for sentence in sentences
                if any(word in sentence.lower() for word in ("believe", "want", "said", "expect"))
            ),
            sentences[0],
        )
        beliefs[client_id] = [
            {
                "id": f"{client_id}:belief:1",
                "text": belief,
                "note_id": latest["note_id"],
                "citations": [f"rm_notes:{latest['note_id']}"],
            }
        ]
    return beliefs


def _gap_matcher(
    facts: dict[str, list[dict[str, Any]]],
    beliefs: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    gaps: dict[str, list[dict[str, Any]]] = {}
    ranking = []
    for client_id, client_facts in facts.items():
        by_key = {fact["id"].rsplit(":", 1)[-1]: fact for fact in client_facts}
        mandate = by_key["mandate-gap"]
        deadline = by_key["deadline"]
        facility = by_key.get("facility")
        concentration = by_key["concentration"]
        belief = beliefs.get(client_id, [{"text": "No note on file.", "citations": []}])[0]
        if client_id == "CL-0003":
            data_text = (
                f"Equity is {mandate['numbers']['actual_pct']:.1f}% against a "
                f"{mandate['numbers']['limit_pct']:.0f}% limit."
            )
            citations = belief["citations"] + [mandate["id"]]
        elif client_id == "CL-0014" and facility:
            data_text = (
                f"Property-linked positions are {concentration['numbers']['weight_pct']:.1f}% "
                f"and facility LTV is {facility['numbers']['ltv_pct']:.2f}%."
            )
            citations = belief["citations"] + [concentration["id"], facility["id"]]
        elif client_id == "CL-0019":
            data_text = (
                f"Shipping and energy-linked positions are "
                f"{concentration['numbers']['weight_pct']:.1f}% of the portfolio."
            )
            citations = belief["citations"] + [concentration["id"]]
        else:
            data_text = mandate["what"] if mandate["numbers"]["gap_pct"] else concentration["what"]
            citations = belief["citations"] + [
                mandate["id"] if mandate["numbers"]["gap_pct"] else concentration["id"]
            ]
        gap = {
            "id": f"{client_id}:gap:1",
            "belief": belief["text"],
            "data": data_text,
            "citations": citations,
        }
        gaps[client_id] = [gap]

        mandate_gap = float(mandate["numbers"]["gap_pct"])
        facility_pressure = 0.0
        if facility:
            facility_pressure = max(0, 20 - float(facility["numbers"]["gap_pct"]) * 5)
        coverage = float(deadline["numbers"].get("coverage_pct", 999))
        liquidity_pressure = max(0, 30 - min(coverage, 100) * 0.3)
        gap_size = min(100, 10 + mandate_gap * 2 + facility_pressure)
        closeness = max(8, 100 - min(float(deadline["numbers"]["days"]), 365) / 4)
        profile = by_key["profile"]["numbers"]
        vulnerability = (10 - float(profile["risk_tolerance_score"])) * 3
        if "inherited" in str(profile["life_stage"]).lower():
            vulnerability += 12
        consequence = min(
            100,
            20
            + mandate_gap
            + facility_pressure * 2
            + liquidity_pressure
            + concentration["numbers"]["weight_pct"] / 4
            + vulnerability,
        )
        weighted_score = (
            gap_size**POLICY.scoring.gap
            * closeness**POLICY.scoring.deadline
            * consequence**POLICY.scoring.consequence
        )
        total_weight = POLICY.scoring.gap + POLICY.scoring.deadline + POLICY.scoring.consequence
        score = round(weighted_score ** (1 / total_weight))
        ranking.append(
            {
                "client_id": client_id,
                "name": by_key["profile"]["numbers"]["name"],
                "score": score,
                "components": {
                    "gap": round(gap_size),
                    "deadline": round(closeness),
                    "consequence": round(consequence),
                },
                "meeting": POLICY.meetings.get(client_id),
                "meeting_source": "Calendar preview" if client_id in POLICY.meetings else None,
                "reason": data_text,
                "urgency": "now" if score >= 65 else "soon" if score >= 45 else "watch",
                "citations": citations,
            }
        )
    ranking.sort(key=lambda item: item["score"], reverse=True)
    return gaps, ranking


def _money(value: float, currency: str) -> str:
    sign = "+" if value >= 0 else "−"
    return f"{sign}{currency} {abs(value) / 1_000_000:.1f}m"


def _narrator(
    facts: dict[str, list[dict[str, Any]]],
    beliefs: dict[str, list[dict[str, Any]]],
    gaps: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Narrate only structured facts, beliefs, and gaps, never source tables."""
    pre_reads: dict[str, dict[str, Any]] = {}
    for client_id, client_facts in facts.items():
        by_key = {fact["id"].rsplit(":", 1)[-1]: fact for fact in client_facts}
        profile = by_key["profile"]
        currency = profile["numbers"]["currency"]
        changes = [fact for fact in client_facts if ":change-" in fact["id"]]
        change_lines = [
            {
                "text": (
                    f"{fact['numbers']['instrument']}: {_money(fact['numbers']['delta'], currency)}"
                ),
                "citations": [fact["id"]],
            }
            for fact in changes
        ]
        rules = []
        mandate = by_key["mandate-gap"]
        if mandate["numbers"]["gap_pct"]:
            rules.append({"text": mandate["what"], "citations": [mandate["id"]]})
        facility = by_key.get("facility")
        if facility:
            rules.append({"text": facility["what"], "citations": [facility["id"]]})
        deadline = by_key["deadline"]
        rules.append({"text": deadline["what"], "citations": [deadline["id"]]})
        default_opening = (
            "You set the limits on this portfolio. Today it sits outside them. "
            "May I show you where?"
        )
        opening = POLICY.openings.get(client_id, default_opening)
        pre_reads[client_id] = {
            "client_id": client_id,
            "name": profile["numbers"]["name"],
            "language": profile["numbers"]["language"],
            "what_changed": change_lines,
            "gap": gaps[client_id][0],
            "rules_money": rules[:3],
            "opening": {"text": opening, "citations": gaps[client_id][0]["citations"]},
            "uncertainty": {
                "text": (
                    "We matched events to holdings by keyword. Confirm external assets and "
                    "ask the client's intent before you advise."
                ),
                "citations": [fact["id"] for fact in changes if fact["event_ids"]],
            },
            "beliefs": beliefs.get(client_id, []),
        }
    return pre_reads


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


def _scenario_engine(
    tables: dict[str, pd.DataFrame],
    evidence: dict[str, dict[str, Any]],
    as_of: date = AS_OF,
) -> dict[str, dict[str, Any]]:
    events = tables["event_log"]
    transmission = events["primary_transmission"]
    related_events = events[transmission.str.contains("shipping|Energy", case=False)]
    event_ids = [
        _add_evidence(
            evidence,
            "event_log",
            row,
            "Hormuz scenario anchor",
            ("event_date", "description", "primary_transmission", "severity"),
        )
        for _, row in related_events.iterrows()
    ]
    scenarios: dict[str, dict[str, Any]] = {}
    current = tables["holdings"][tables["holdings"]["snapshot_date"] == as_of.isoformat()]
    for client_id, rows in current.groupby("client_id"):
        currency = str(rows["portfolio_ccy"].iloc[0])
        total = float(rows["market_value_base"].sum())
        client_scenarios = {}
        for scenario_name, shocks in POLICY.shocks.items():
            grouped: dict[str, dict[str, Any]] = {}
            low_total = high_total = 0.0
            for _, row in rows.iterrows():
                theme = _theme(row)
                low_shock, high_shock = shocks[theme]
                value = float(row["market_value_base"])
                low_delta, high_delta = value * low_shock, value * high_shock
                low_total += low_delta
                high_total += high_delta
                item = grouped.setdefault(theme, {"low": 0.0, "high": 0.0, "citations": []})
                item["low"] += low_delta
                item["high"] += high_delta
                item["citations"].append(
                    _add_evidence(
                        evidence,
                        "holdings",
                        row,
                        "Scenario input holding",
                        (
                            "snapshot_date",
                            "portfolio_id",
                            "instrument_id",
                            "instrument_name",
                            "asset_class",
                            "sector",
                            "market_value_base",
                        ),
                    )
                )
            bullets = []
            ranked = sorted(
                grouped.items(),
                key=lambda item: max(abs(item[1]["low"]), abs(item[1]["high"])),
                reverse=True,
            )
            for theme, values in ranked[:3]:
                bullets.append(
                    {
                        "text": (
                            f"{theme}: {_money(values['low'], currency)} to "
                            f"{_money(values['high'], currency)}"
                        ),
                        "low_delta": round(values["low"], 2),
                        "high_delta": round(values["high"], 2),
                        "citations": values["citations"] + event_ids,
                    }
                )
            client_scenarios[scenario_name] = {
                "name": "Strait reopens" if scenario_name == "reopens" else "Strait escalates",
                "currency": currency,
                "portfolio_value": total,
                "low_delta": round(min(low_total, high_total), 2),
                "high_delta": round(max(low_total, high_total), 2),
                "low_pct": round(min(low_total, high_total) / total * 100, 1),
                "high_pct": round(max(low_total, high_total) / total * 100, 1),
                "bullets": bullets,
                "citations": event_ids,
                "disclaimer": POLICY.scenario_disclaimer,
            }
        scenarios[str(client_id)] = client_scenarios
    return scenarios


def _workflow(
    clients: pd.DataFrame,
    notes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for _, client in clients.iterrows():
        client_id = str(client["client_id"])
        client_notes = [note for note in notes if note["client_id"] == client_id]
        latest = max(client_notes, key=lambda item: item["note_date"])
        email = max(
            (note for note in client_notes if note["channel"] == "Email"),
            key=lambda item: item["note_date"],
            default=None,
        )
        meeting = max(
            (note for note in client_notes if note["channel"] == "Meeting"),
            key=lambda item: item["note_date"],
            default=None,
        )
        latest_citation = f"rm_notes:{latest['note_id']}"
        profile_citation = f"clients:{client_id}"
        result[client_id] = [
            {
                "system": "CRM",
                "status": f"{latest['channel']} logged {latest['note_date']}",
                "citations": [latest_citation],
            },
            {
                "system": "Gmail",
                "status": f"Last email {email['note_date']}" if email else "No thread linked",
                "citations": [f"rm_notes:{email['note_id']}" if email else profile_citation],
            },
            {
                "system": "Teams",
                "status": (
                    f"Meeting {meeting['note_date']}; no transcript"
                    if meeting
                    else "No meeting linked"
                ),
                "citations": [f"rm_notes:{meeting['note_id']}" if meeting else profile_citation],
            },
            {
                "system": "Map",
                "status": (
                    f"{client['country_of_residence']} client; {client['booking_centre']} booking"
                ),
                "citations": [profile_citation],
            },
            {
                "system": "Notes",
                "status": latest["note"],
                "citations": [latest_citation],
            },
        ]
    return result


def _build_projection(
    tables: dict[str, pd.DataFrame],
    notes: list[dict[str, Any]],
    as_of: date = AS_OF,
) -> dict[str, Any]:
    facts, evidence = _fact_engine(tables, as_of)
    beliefs = _belief_extractor(notes, evidence)
    gaps, ranking = _gap_matcher(facts, beliefs)
    pre_reads = _narrator(facts, beliefs, gaps)
    scenarios = _scenario_engine(tables, evidence, as_of)
    workflows = _workflow(tables["clients"], notes)
    for client_id, pre_read in pre_reads.items():
        pre_read["workflow"] = workflows[client_id]
    return {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "pipeline": ["Fact engine", "Belief extractor", "Gap matcher", "Narrator", "Review log"],
        "ranking_formula": "gap size × deadline closeness × consequence",
        "ranking": ranking,
        "facts": facts,
        "pre_reads": pre_reads,
        "scenarios": scenarios,
        "evidence": evidence,
    }
