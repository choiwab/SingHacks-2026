"""Regression checks for as-of evidence and complete formula inputs."""

import re
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.analytics.facts import fact_engine
from app.pipeline import evidence_id, load_sources

DATA = Path(__file__).resolve().parents[1] / "data"
SNAPSHOTS = ("2025-12-31", "2026-02-27", "2026-03-31", "2026-06-30", "2026-08-26")


@pytest.mark.parametrize("snapshot", SNAPSHOTS)
def test_facts_and_evidence_use_requested_snapshot(snapshot: str) -> None:
    as_of = date.fromisoformat(snapshot)
    tables, _ = load_sources(DATA, as_of=as_of)
    facts, evidence = fact_engine(tables, as_of)

    assert len(facts) == 20
    for entry in evidence.values():
        record = entry["record"]
        for field in ("snapshot_date", "event_date"):
            if field in record:
                assert record[field] <= snapshot
        for field in record:
            dated_column = re.search(r"(\d{4}-\d{2}-\d{2})$", field)
            if dated_column:
                assert dated_column[1] <= snapshot

    for client_id, client_facts in facts.items():
        rows = tables["holdings"][tables["holdings"]["client_id"] == client_id]
        for fact in client_facts:
            if ":fact:change-" not in fact["id"]:
                continue
            supporting = [evidence[citation]["record"] for citation in fact["source_rows"]]
            assert {row["snapshot_date"] for row in supporting} <= {SNAPSHOTS[0], snapshot}
            instrument_id = supporting[0]["instrument_id"]
            positions = rows[rows["instrument_id"] == instrument_id]
            baseline = positions[positions["snapshot_date"] == SNAPSHOTS[0]]
            current = positions[positions["snapshot_date"] == snapshot]
            expected = current["market_value_base"].sum() - baseline["market_value_base"].sum()
            assert fact["numbers"]["delta"] == round(float(expected), 2)

    facilities = tables["credit_facilities"]
    for client_id in facilities["client_id"].unique():
        fact = next(item for item in facts[client_id] if item["id"].endswith(":facility"))
        expected = facilities[facilities["client_id"] == client_id][f"ltv_pct_{snapshot}"].max()
        assert fact["numbers"]["ltv_pct"] == expected


def test_future_rows_cannot_change_historical_facts() -> None:
    as_of = date(2026, 6, 30)
    tables, _ = load_sources(DATA, as_of=as_of)
    expected = fact_engine(tables, as_of)
    holdings = tables["holdings"]
    future = holdings["snapshot_date"] > as_of.isoformat()
    holdings.loc[future, "instrument_name"] = "Future-only instrument name"
    holdings.loc[future, "market_value_base"] = 999_999_999
    event = tables["event_log"].iloc[[0]].copy()
    event["event_date"] = "2026-09-01"
    event["description"] = "Future-only event"
    event["primary_transmission"] = " ".join(holdings["instrument_name"].unique())
    tables["event_log"] = pd.concat([tables["event_log"], event], ignore_index=True)
    for column in tables["credit_facilities"].columns:
        if column.endswith("2026-08-26"):
            tables["credit_facilities"][column] = 999_999_999

    assert fact_engine(tables, as_of) == expected


def test_denominator_liquidity_and_kyc_inputs_are_cited() -> None:
    as_of = date(2026, 8, 26)
    tables, _ = load_sources(DATA, as_of=as_of)
    facts, evidence = fact_engine(tables, as_of)
    for client_id, client_facts in facts.items():
        holdings = tables["holdings"]
        current = holdings.query(
            "client_id == @selected and snapshot_date == '2026-08-26'",
            local_dict={"selected": client_id},
        )
        holding_ids = {evidence_id("holdings", row) for _, row in current.iterrows()}
        for key in ("mandate-gap", "concentration"):
            fact = next(item for item in client_facts if item["id"].endswith(f":{key}"))
            assert holding_ids <= set(fact["source_rows"])
        deadline = next(item for item in client_facts if item["id"].endswith(":deadline"))
        if "daily_liquid" in deadline["numbers"]:
            daily_ids = {
                evidence_id("holdings", row)
                for _, row in current[current["liquidity_tier"] == "Daily"].iterrows()
            }
            assert daily_ids <= set(deadline["source_rows"])
            assert all(evidence[item]["record"]["liquidity_tier"] == "Daily" for item in daily_ids)

    tables["planned_cash_needs"] = tables["planned_cash_needs"].iloc[:0]
    facts, evidence = fact_engine(tables, as_of)
    for client_id, client_facts in facts.items():
        deadline = next(item for item in client_facts if item["id"].endswith(":deadline"))
        assert deadline["source_rows"] == [f"clients:{client_id}"]
        assert "kyc_review_due" in evidence[deadline["source_rows"][0]]["record"]
