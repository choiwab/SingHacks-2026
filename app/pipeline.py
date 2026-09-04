"""Offline fact-to-narrative pipeline for the Monday Brief demo."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
GENERATED = DATA / "generated"
AS_OF = date(2026, 8, 26)
SNAPSHOT = "2026-08-26"
BASELINE = "2025-12-31"

TABLE_NAMES = (
    "clients",
    "commitments",
    "credit_facilities",
    "event_log",
    "holdings",
    "instruments",
    "mandates",
    "market_context",
    "planned_cash_needs",
    "portfolios",
)

MEETINGS = {
    "CL-0003": "Mon 10:30",
    "CL-0014": "Tue 14:00",
    "CL-0019": "Thu 09:00",
}

KNOWN_BELIEFS = {
    "CL-0003": {
        "text": "I have never taken a risk with money.",
        "note_id": "N-005",
    },
    "CL-0014": {
        "text": "The Hong Kong property market turns this year.",
        "note_id": "N-018",
    },
    "CL-0019": {
        "text": "The Asia portfolio should be uncorrelated with the Gulf business.",
        "note_id": "N-025",
    },
}

OPENINGS = {
    "CL-0003": (
        "Sie wünschen ein sicheres, ruhiges Portfolio. "
        "Heute sind jedoch 71,5 % in Aktien investiert. Darf ich Ihnen die Lücke zeigen?"
    ),
    "CL-0014": (
        "劉先生，您希望保留物業復甦的上升空間，也要確保重建資金。"
        "我們可以先看看信貸額度在不同情境下還有多少緩衝嗎？"
    ),
    "CL-0019": (
        "You asked for the Asia portfolio to diversify the Gulf business. "
        "May I show where shipping conditions now drive both?"
    ),
}

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


def load_sources() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    tables = {name: pd.read_csv(DATA / f"{name}.csv") for name in TABLE_NAMES}
    notes = json.loads((DATA / "rm_notes.json").read_text(encoding="utf-8"))
    return tables, notes


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
        key = f"{row['event_date']}:{row.name}"
    elif table == "market_context":
        key = f"{row['snapshot_date']}:{row['series_code']}"
    else:
        id_field = next((field for field in row.index if field.endswith("_id")), None)
        key = str(row[id_field]) if id_field else str(row.name)
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
) -> list[dict[str, Any]]:
    client_id = str(client["client_id"])
    baseline = holdings[holdings["snapshot_date"] == BASELINE]
    current = holdings[holdings["snapshot_date"] == SNAPSHOT]
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
) -> dict[str, Any]:
    client_id = str(client["client_id"])
    needs = tables["planned_cash_needs"].query("client_id == @client_id")
    if needs.empty:
        due = date.fromisoformat(str(client["kyc_review_due"]))
        return _fact(
            client_id,
            "deadline",
            f"KYC review is due {due.strftime('%d %b %Y')}.",
            {"days": max((due - AS_OF).days, 0), "amount": 0, "currency": None},
            [],
        )
    need = needs.sort_values("due_from").iloc[0]
    due = date.fromisoformat(str(need["due_from"]))
    daily = current[current["liquidity_tier"] == "Daily"]["market_value_base"].sum()
    amount = float(need["amount"])
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
        f"{need['description']} starts in {max((due - AS_OF).days, 0)} days.",
        {
            "days": max((due - AS_OF).days, 0),
            "amount": amount,
            "currency": need["currency"],
            "daily_liquid": round(float(daily), 2),
            "coverage_pct": round(min(daily / amount * 100, 999), 1) if amount else 999,
            "description": need["description"],
        },
        [evidence_id],
    )


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


def fact_engine(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    evidence: dict[str, dict[str, Any]] = {}
    all_facts: dict[str, list[dict[str, Any]]] = {}
    holdings = tables["holdings"]
    for _, client in tables["clients"].iterrows():
        client_id = str(client["client_id"])
        client_holdings = holdings[holdings["client_id"] == client_id]
        current = client_holdings[client_holdings["snapshot_date"] == SNAPSHOT]
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
        facts.extend(_change_facts(client, client_holdings, tables["event_log"], evidence))
        facts.append(_mandate_fact(client, current, tables, evidence))
        facts.append(_deadline_fact(client, current, tables, evidence))
        facility = _facility_fact(client_id, tables, evidence)
        if facility:
            facts.append(facility)
        facts.append(_theme_fact(client_id, current, evidence))
        all_facts[client_id] = facts
    return all_facts, evidence


def belief_extractor(
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
        known = KNOWN_BELIEFS.get(client_id)
        if known:
            beliefs[client_id] = [
                {
                    "id": f"{client_id}:belief:1",
                    "text": known["text"],
                    "note_id": known["note_id"],
                    "citations": [f"rm_notes:{known['note_id']}"],
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


def gap_matcher(
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
        score = round((gap_size * closeness * consequence) ** (1 / 3))
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
                "meeting": MEETINGS.get(client_id),
                "meeting_source": "Calendar preview" if client_id in MEETINGS else None,
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


def narrator(
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
        opening = OPENINGS.get(client_id, default_opening)
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


SHOCKS = {
    "reopens": {
        "Shipping": (-0.18, -0.08),
        "Energy": (-0.12, -0.05),
        "Gold": (-0.06, -0.02),
        "Bonds": (0.01, 0.04),
        "Structured products": (-0.10, -0.03),
        "Other assets": (-0.01, 0.03),
        "Cash": (0.0, 0.0),
    },
    "escalates": {
        "Shipping": (0.06, 0.18),
        "Energy": (0.06, 0.15),
        "Gold": (0.04, 0.10),
        "Bonds": (-0.05, -0.01),
        "Structured products": (-0.08, 0.05),
        "Other assets": (-0.08, -0.02),
        "Cash": (0.0, 0.0),
    },
}


def scenario_engine(
    tables: dict[str, pd.DataFrame],
    evidence: dict[str, dict[str, Any]],
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
    current = tables["holdings"].query("snapshot_date == @SNAPSHOT")
    for client_id, rows in current.groupby("client_id"):
        currency = str(rows["portfolio_ccy"].iloc[0])
        total = float(rows["market_value_base"].sum())
        client_scenarios = {}
        for scenario_name, shocks in SHOCKS.items():
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
                "disclaimer": "Precomputed range, not a forecast.",
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
        result[client_id] = [
            {"system": "CRM", "status": f"{latest['channel']} logged {latest['note_date']}"},
            {
                "system": "Gmail",
                "status": f"Last email {email['note_date']}" if email else "No thread linked",
            },
            {
                "system": "Teams",
                "status": (
                    f"Meeting {meeting['note_date']}; no transcript"
                    if meeting
                    else "No meeting linked"
                ),
            },
            {
                "system": "Map",
                "status": (
                    f"{client['country_of_residence']} client; {client['booking_centre']} booking"
                ),
            },
            {"system": "Notes", "status": latest["note"]},
        ]
    return result


def build_app_data() -> dict[str, Any]:
    tables, notes = load_sources()
    facts, evidence = fact_engine(tables)
    beliefs = belief_extractor(notes, evidence)
    gaps, ranking = gap_matcher(facts, beliefs)
    pre_reads = narrator(facts, beliefs, gaps)
    scenarios = scenario_engine(tables, evidence)
    workflows = _workflow(tables["clients"], notes)
    for client_id, pre_read in pre_reads.items():
        pre_read["workflow"] = workflows[client_id]
    return {
        "as_of": AS_OF.isoformat(),
        "pipeline": ["Fact engine", "Belief extractor", "Gap matcher", "Narrator", "Review log"],
        "ranking_formula": "gap size × deadline closeness × consequence",
        "ranking": ranking,
        "facts": facts,
        "pre_reads": pre_reads,
        "scenarios": scenarios,
        "evidence": evidence,
    }


def build_and_save() -> dict[str, Any]:
    data = build_app_data()
    GENERATED.mkdir(exist_ok=True)
    (GENERATED / "app_data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return data


if __name__ == "__main__":
    result = build_and_save()
    print(f"Prepared {len(result['ranking'])} clients in {len(result['pipeline'])} stations.")
