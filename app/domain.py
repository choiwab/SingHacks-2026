"""Deterministic client-state, scenario, and decision-support services."""

from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AS_OF_DATE = "2026-08-26"
CLIENT_ID = "CL-0014"
PROPERTY_IDS = {
    "SYN-FI-0207",
    "SYN-ST-0106",
    "SYN-SP-0503",
    "SYN-AL-0307",
}
SCENARIO_SHOCKS = {
    "SYN-FI-0207": Decimal("-0.15"),
    "SYN-FI-0206": Decimal("-0.02"),
    "SYN-ST-0106": Decimal("-0.15"),
    "SYN-SP-0503": Decimal("-0.15"),
    "SYN-EQ-0021": Decimal("-0.05"),
    "SYN-FI-0205": Decimal("-0.03"),
    "SYN-AL-0307": Decimal("-0.15"),
    "SYN-CA-0603": Decimal("0"),
}


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_notes() -> list[dict[str, str]]:
    with (DATA / "rm_notes.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _one(rows: list[dict[str, str]], **matches: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in matches.items()):
            return row
    criteria = ", ".join(f"{key}={value}" for key, value in matches.items())
    raise LookupError(f"No row found for {criteria}")


def _decimal(row: dict[str, str], key: str) -> Decimal:
    return Decimal(row[key])


def _number(value: Decimal, places: str = "0.01") -> float:
    return float(value.quantize(Decimal(places)))


def _money_m(value: Decimal) -> float:
    return _number(value / Decimal("1000000"))


@dataclass(frozen=True)
class CaseRows:
    client: dict[str, str]
    portfolio: dict[str, str]
    facility: dict[str, str]
    cash_need: dict[str, str]
    holdings: tuple[dict[str, str], ...]
    notes: tuple[dict[str, str], ...]
    events: tuple[dict[str, str], ...]


def load_case_rows() -> CaseRows:
    client = _one(_read_csv("clients.csv"), client_id=CLIENT_ID)
    portfolio = _one(_read_csv("portfolios.csv"), client_id=CLIENT_ID)
    facility = _one(_read_csv("credit_facilities.csv"), client_id=CLIENT_ID)
    cash_need = _one(_read_csv("planned_cash_needs.csv"), client_id=CLIENT_ID)
    holdings = tuple(
        row
        for row in _read_csv("holdings.csv")
        if row["client_id"] == CLIENT_ID and row["snapshot_date"] == AS_OF_DATE
    )
    notes = tuple(row for row in _read_notes() if row["client_id"] == CLIENT_ID)
    events = tuple(row for row in _read_csv("event_log.csv") if row["event_date"] <= AS_OF_DATE)
    if len(holdings) != 8:
        raise ValueError(f"Expected 8 current Lau holdings, found {len(holdings)}")
    return CaseRows(client, portfolio, facility, cash_need, holdings, notes, events)


def build_case_summary() -> dict[str, Any]:
    rows = load_case_rows()
    current_value = sum(_decimal(row, "market_value_base") for row in rows.holdings)
    property_value = sum(
        _decimal(row, "market_value_base")
        for row in rows.holdings
        if row["instrument_id"] in PROPERTY_IDS
    )
    facility_drawn = _decimal(rows.facility, f"drawn_{AS_OF_DATE}")
    lending_value = _decimal(rows.facility, f"lending_value_{AS_OF_DATE}")
    trigger = _decimal(rows.facility, "margin_call_ltv_pct")
    trigger_lending_value = facility_drawn / (trigger / Decimal("100"))
    current_ltv = facility_drawn / lending_value * Decimal("100")
    known_cash = sum(
        _decimal(row, "market_value_base")
        for row in rows.holdings
        if row["asset_class"] == "Cash and Equivalents"
    )
    need = _decimal(rows.cash_need, "amount")

    ltv_history = []
    for snapshot in (
        "2025-12-31",
        "2026-02-27",
        "2026-03-31",
        "2026-06-30",
        "2026-08-26",
    ):
        ltv_history.append(
            {
                "date": snapshot,
                "label": {
                    "2025-12-31": "Dec 25",
                    "2026-02-27": "Feb 26",
                    "2026-03-31": "Mar 26",
                    "2026-06-30": "Jun 26",
                    "2026-08-26": "Today",
                }[snapshot],
                "ltv": float(rows.facility[f"ltv_pct_{snapshot}"]),
            }
        )

    return {
        "as_of": AS_OF_DATE,
        "client": {
            "id": rows.client["client_id"],
            "name": rows.client["client_name"],
            "age": int(rows.client["age"]),
            "booking_centre": rows.client["booking_centre"],
            "risk_profile": rows.client["risk_profile"],
            "risk_tolerance": int(rows.client["risk_tolerance_score"]),
            "liquidity_need": rows.client["liquidity_needs"],
            "source_of_wealth": rows.client["source_of_wealth"],
            "objective": rows.client["objectives"],
            "kyc_due": rows.client["kyc_review_due"],
            "rm_name": rows.client["rm_name"],
        },
        "portfolio": {
            "id": rows.portfolio["portfolio_id"],
            "name": rows.portfolio["portfolio_name"],
            "currency": rows.portfolio["base_currency"],
            "aum_m": _money_m(current_value),
            "property_value_m": _money_m(property_value),
            "property_weight_pct": _number(property_value / current_value * Decimal("100")),
            "known_cash_m": _money_m(known_cash),
            "cash_coverage_pct": _number(known_cash / need * Decimal("100")),
        },
        "facility": {
            "id": rows.facility["facility_id"],
            "type": rows.facility["facility_type"],
            "limit_m": _money_m(_decimal(rows.facility, "credit_limit")),
            "drawn_m": _money_m(facility_drawn),
            "lending_value_m": _money_m(lending_value),
            "ltv_pct": _number(current_ltv),
            "trigger_pct": _number(trigger),
            "decline_to_trigger_pct": _number(
                (lending_value - trigger_lending_value) / lending_value * Decimal("100")
            ),
            "history": ltv_history,
        },
        "cash_need": {
            "id": rows.cash_need["need_id"],
            "description": rows.cash_need["description"],
            "amount_m": _money_m(need),
            "currency": rows.cash_need["currency"],
            "due": rows.cash_need["due_to"],
            "certainty": rows.cash_need["certainty"],
        },
        "attention": (
            "Lau's property exposure, secured borrowing, and HKD 60 million "
            "redevelopment need depend on the same market outcome."
        ),
        "governance_notice": (
            "No Hong Kong property catalyst appears in the controlled event log through "
            "26 August 2026. The stress below is a hypothetical scenario, not a forecast."
        ),
    }


def run_scenario() -> dict[str, Any]:
    rows = load_case_rows()
    scenario_holdings = []
    current_total = Decimal("0")
    stressed_total = Decimal("0")
    stressed_lending = Decimal("0")

    for row in rows.holdings:
        current_value = _decimal(row, "market_value_base")
        advance_rate = _decimal(row, "advance_rate_pct") / Decimal("100")
        shock = SCENARIO_SHOCKS[row["instrument_id"]]
        stressed_value = current_value * (Decimal("1") + shock)
        holding = {
            "instrument_id": row["instrument_id"],
            "name": row["instrument_name"],
            "asset_class": row["asset_class"],
            "theme": (
                "Hong Kong property" if row["instrument_id"] in PROPERTY_IDS else row["sector"]
            ),
            "property_linked": row["instrument_id"] in PROPERTY_IDS,
            "current_value_m": _money_m(current_value),
            "portfolio_weight_pct": _number(_decimal(row, "weight_pct")),
            "liquidity": row["liquidity_tier"],
            "advance_rate_pct": _number(_decimal(row, "advance_rate_pct")),
            "lending_value_m": _money_m(_decimal(row, "lending_value_base")),
            "shock_pct": _number(shock * Decimal("100")),
            "stressed_value_m": _money_m(stressed_value),
            "evidence_id": f"holding:{row['instrument_id']}",
        }
        scenario_holdings.append(holding)
        current_total += current_value
        stressed_total += stressed_value
        stressed_lending += stressed_value * advance_rate

    facility_drawn = _decimal(rows.facility, f"drawn_{AS_OF_DATE}")
    current_lending = _decimal(rows.facility, f"lending_value_{AS_OF_DATE}")
    trigger = _decimal(rows.facility, "margin_call_ltv_pct") / Decimal("100")
    stressed_ltv = facility_drawn / stressed_lending * Decimal("100")
    cure = max(Decimal("0"), facility_drawn - trigger * stressed_lending)

    scenario_holdings.sort(key=lambda item: (not item["property_linked"], -item["current_value_m"]))
    return {
        "name": "Moderate Hong Kong Property Stress",
        "kind": "Hypothetical scenario",
        "is_forecast": False,
        "assumptions": [
            "Four direct and look-through property positions decline 15%.",
            "Greater China equities decline 5% and Asia high yield declines 3%.",
            "The accumulator uses a simplified mark-to-market shock, not a full payoff model.",
            "Facility drawings remain HKD 58 million throughout the stress.",
        ],
        "current": {
            "portfolio_value_m": _money_m(current_total),
            "lending_value_m": _money_m(current_lending),
            "ltv_pct": _number(facility_drawn / current_lending * Decimal("100")),
        },
        "stressed": {
            "portfolio_value_m": _money_m(stressed_total),
            "portfolio_change_m": _money_m(stressed_total - current_total),
            "portfolio_change_pct": _number(
                (stressed_total - current_total) / current_total * Decimal("100")
            ),
            "lending_value_m": _money_m(stressed_lending),
            "lending_change_m": _money_m(stressed_lending - current_lending),
            "ltv_pct": _number(stressed_ltv),
            "trigger_breached": stressed_ltv >= trigger * Decimal("100"),
            "cure_m": _money_m(cure),
        },
        "holdings": scenario_holdings,
    }


async def _specialist(
    role: str,
    stance: str,
    position: str,
    concern: str,
    action: str,
    evidence_ids: list[str],
    confidence: str = "High",
) -> dict[str, Any]:
    await asyncio.sleep(0)
    return {
        "role": role,
        "stance": stance,
        "position": position,
        "concern": concern,
        "action": action,
        "evidence_ids": evidence_ids,
        "confidence": confidence,
    }


async def run_specialist_council() -> list[dict[str, Any]]:
    return list(
        await asyncio.gather(
            _specialist(
                "Lending",
                "Protect now",
                "Restore a meaningful collateral buffer before another property-linked decline.",
                "The current 69.41% LTV is only about 0.85% of lending value from the trigger.",
                "Confirm external HKD liquidity and model buffer targets with Credit.",
                ["facility:CF-0002", "scenario:moderate-property"],
            ),
            _specialist(
                "Liquidity",
                "Preserve the project",
                "Ring-fence the redevelopment plan before choosing a facility cure source.",
                "Known portfolio cash is HKD 12 million against a confirmed HKD 60 million need.",
                "Map external liquidity and sequence the facility and project funding decisions.",
                ["cash-need:CN-013", "holding:SYN-CA-0603", "note:N-019"],
            ),
            _specialist(
                "Portfolio",
                "Reduce in stages",
                "Reduce duplicated exposure without forcing Lau to abandon his recovery view.",
                "Four property-linked positions represent about 49% of the current portfolio.",
                "Compare staged reductions by liquidity, collateral value, and mandate impact.",
                [
                    "holding:SYN-FI-0207",
                    "holding:SYN-ST-0106",
                    "holding:SYN-SP-0503",
                    "holding:SYN-AL-0307",
                ],
            ),
            _specialist(
                "Client perspective",
                "Retain conviction",
                "Lau is likely to resist a proposal framed as abandoning Hong Kong property.",
                "He describes the repeated exposure as the reason for his confidence.",
                (
                    "Frame resilience as protecting the redevelopment project, not challenging "
                    "his forecast."
                ),
                ["note:N-018", "note:N-019"],
            ),
            _specialist(
                "Risk red team",
                "Verify first",
                "The consequence is defensible, but the scenario is not a market prediction.",
                (
                    "External liquidity is unknown and the accumulator shock is deliberately "
                    "simplified."
                ),
                "Label assumptions and obtain specialist review before any client recommendation.",
                ["scenario:moderate-property", "data-gap:external-liquidity"],
                "Medium",
            ),
        )
    )


def build_evidence() -> dict[str, dict[str, Any]]:
    rows = load_case_rows()
    evidence: dict[str, dict[str, Any]] = {
        "facility:CF-0002": {
            "title": "Current Lombard facility",
            "type": "Observed fact",
            "source": "credit_facilities.csv",
            "record": "CF-0002",
            "as_of": AS_OF_DATE,
            "detail": "HKD 58.00m drawn; HKD 83.57m lending value; 69.41% LTV; 70.00% trigger.",
        },
        "cash-need:CN-013": {
            "title": "Redevelopment contribution",
            "type": "Observed fact",
            "source": "planned_cash_needs.csv",
            "record": "CN-013",
            "as_of": "2026-08-26",
            "detail": "HKD 60.00m confirmed equity contribution due by 30 June 2027.",
        },
        "note:N-018": {
            "title": "Client's property conviction",
            "type": "RM note",
            "source": "rm_notes.json",
            "record": "N-018",
            "as_of": "2026-03-05",
            "detail": rows.notes[0]["note"],
        },
        "note:N-019": {
            "title": "Client's liquidity surprise",
            "type": "RM note",
            "source": "rm_notes.json",
            "record": "N-019",
            "as_of": "2026-08-11",
            "detail": rows.notes[1]["note"],
        },
        "scenario:moderate-property": {
            "title": "Moderate property stress",
            "type": "Scenario assumption",
            "source": "RM-defined scenario",
            "record": "SCN-HKPROP-01",
            "as_of": AS_OF_DATE,
            "detail": (
                "Hypothetical shocks are applied deterministically. The event log supplies no "
                "property catalyst."
            ),
            "formula": "stressed LTV = drawn amount / sum(stressed value x advance rate)",
        },
        "data-gap:external-liquidity": {
            "title": "External liquidity is unknown",
            "type": "Data-quality warning",
            "source": "Coverage gap",
            "record": "GAP-001",
            "as_of": AS_OF_DATE,
            "detail": "The supplied data contains no verified external cash available to Lau.",
        },
    }
    for row in rows.holdings:
        evidence[f"holding:{row['instrument_id']}"] = {
            "title": row["instrument_name"],
            "type": "Observed holding",
            "source": "holdings.csv",
            "record": f"{AS_OF_DATE} / {row['portfolio_id']} / {row['instrument_id']}",
            "as_of": AS_OF_DATE,
            "detail": (
                f"HKD {_money_m(_decimal(row, 'market_value_base')):.2f}m market value; "
                f"{_number(_decimal(row, 'weight_pct')):.2f}% portfolio weight; "
                f"{row['liquidity_tier']} liquidity; {row['advance_rate_pct']}% advance rate."
            ),
        }
    return evidence


def build_action_plan() -> dict[str, Any]:
    return {
        "status": "Draft for RM review",
        "summary": (
            "Protect the redevelopment plan by confirming available HKD liquidity and agreeing "
            "how much risk the project can tolerate before choosing how to restore a facility "
            "buffer."
        ),
        "tasks": [
            {
                "id": "TASK-01",
                "title": "Confirm external HKD liquidity available for a facility cure",
                "owner": "Lau Chi Ming",
                "due": "2026-09-05",
                "system": "CRM task",
                "evidence_ids": ["cash-need:CN-013", "data-gap:external-liquidity"],
            },
            {
                "id": "TASK-02",
                "title": "Convene a joint lending and portfolio review",
                "owner": "Priscilla Ong",
                "due": "2026-09-08",
                "system": "Calendar",
                "evidence_ids": ["facility:CF-0002", "scenario:moderate-property"],
            },
            {
                "id": "TASK-03",
                "title": "Compare staged options for restoring an LTV buffer",
                "owner": "Lending specialist",
                "due": "2026-09-12",
                "system": "Specialist case",
                "evidence_ids": ["scenario:moderate-property"],
            },
        ],
        "open_questions": [
            (
                "How much external HKD liquidity is available without weakening the "
                "redevelopment plan?"
            ),
            "What collateral buffer would Lau accept while retaining part of the property view?",
            "Which positions can be reduced without misrepresenting accumulator liquidity?",
        ],
    }


def rehearse(opening: str, follow_up: str | None = None) -> dict[str, Any]:
    valid_openings = {"trigger", "project", "concentration"}
    valid_follow_ups = {"challenge", "resilience", "sell"}
    if opening not in valid_openings:
        raise ValueError("Choose a supported opening approach")
    if follow_up is not None and follow_up not in valid_follow_ups:
        raise ValueError("Choose a supported follow-up approach")

    opening_feedback = {
        "trigger": (
            "The urgency is clear, but the opening risks making the facility feel like the "
            "bank's problem rather than Lau's goal."
        ),
        "project": (
            "This begins with Lau's objective and creates permission to discuss the collateral "
            "risk."
        ),
        "concentration": (
            "The observation is correct, but it can sound like a challenge to Lau's expertise "
            "and conviction."
        ),
    }[opening]
    result: dict[str, Any] = {
        "client_position": "I still believe the Hong Kong property market turns this year.",
        "opening_feedback": opening_feedback,
        "evidence_ids": ["note:N-018", "note:N-019"],
    }
    if follow_up is None:
        return result

    outcomes = {
        "challenge": {
            "status": "Defensive",
            "headline": "The conversation turns into a market debate.",
            "coaching": (
                "Acknowledge the recovery view, then separate that conviction from the project's "
                "funding resilience."
            ),
            "next_question": "How much of the project can remain exposed to the same market view?",
        },
        "resilience": {
            "status": "Constructive next step",
            "headline": "Lau agrees to test resilience without abandoning his view.",
            "coaching": (
                "You protected the client's objective, used the trigger as evidence, and moved "
                "toward a review rather than a forced sale."
            ),
            "next_question": (
                "What external HKD liquidity can we confirm before the specialist review?"
            ),
        },
        "sell": {
            "status": "Stalled",
            "headline": "The proposed transaction arrives before the constraints are understood.",
            "coaching": (
                "Confirm external liquidity and acceptable safeguards before selecting a product "
                "or sale path."
            ),
            "next_question": "Which outcomes must a solution preserve for you?",
        },
    }
    result.update(outcomes[follow_up])
    return result


def build_connector_previews(tasks: list[dict[str, str]]) -> dict[str, Any]:
    task_titles = [task["title"] for task in tasks]
    return {
        "approval_id": f"APR-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "status": "Approved for preview only",
        "writes_executed": 0,
        "connectors": [
            {
                "name": "Calendar",
                "destination": "Priscilla Ong / Private calendar",
                "mode": "Create event preview",
                "payload": {
                    "title": "Lau Chi Ming - funding resilience review",
                    "date": "2026-09-08 10:00 HKT",
                    "attendees": "Client, RM, Lending, Portfolio",
                },
            },
            {
                "name": "Client email",
                "destination": "CRM-linked email drafts",
                "mode": "Draft only",
                "payload": {
                    "subject": "Redevelopment funding resilience review",
                    "body": (
                        "Thank you for discussing how we can protect the redevelopment timeline "
                        "while preserving flexibility. I have prepared a joint review with our "
                        "lending and portfolio specialists."
                    ),
                },
            },
            {
                "name": "CRM and tasks",
                "destination": "Client CL-0014 / interaction record",
                "mode": "Write-back preview",
                "payload": {"stage": "Serve and deepen", "tasks": task_titles},
            },
            {
                "name": "Document record",
                "destination": "Client CL-0014 / Advisory records",
                "mode": "Save preview",
                "payload": {
                    "filename": "2026-08-26_lau-funding-resilience-brief.pdf",
                    "classification": "Confidential client record",
                },
            },
        ],
        "outcome": {
            "client_goal": "Redevelopment funding resilience advanced",
            "risk_obligation": "LTV buffer review assigned",
            "relationship_stage": "Specialist review prepared",
            "records": "CRM note, tasks, calendar event, and brief ready to sync",
            "revenue": None,
            "revenue_note": (
                "Not estimated because governed pricing and attribution data are unavailable."
            ),
        },
    }
