"""Risk-policy boundaries and source provenance for the reviewed Phase A specification."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.analytics.phase_a import PhaseAContext
from app.analytics.phase_a_performance import compute_performance
from app.analytics.phase_a_risk import _RiskEngine, compute_risk
from app.pipeline.evidence import evidence_id
from app.pipeline.stages.clean import clean_sources
from app.pipeline.stages.ingest import ingest_sources

DATA = Path(__file__).resolve().parents[1] / "data"


def make_context(as_of=date(2026, 8, 26)):
    sources = ingest_sources(DATA, as_of=as_of)
    return PhaseAContext(clean_sources(sources.tables, sources.notes, as_of=as_of), "risk-test")


@pytest.fixture(scope="module")
def reviewed_context():
    context = make_context()
    compute_performance(context)
    compute_risk(context)
    return context


def facts_of(context, client_id, kind):
    return [fact for fact in context.facts[client_id] if fact.kind == kind]


def signals_of(context, kind):
    return [
        signal for signals in context.signals.values() for signal in signals if signal.kind == kind
    ]


def test_issuer_defaults_hidden_exposure_and_unknown_basket_are_independent(reviewed_context):
    context = reviewed_context
    lau = {
        fact.inputs["issuer"]: fact.value
        for fact in facts_of(context, "CL-0014", "concentration.lookthrough_pct")
    }
    assert lau["Golden Harbour Properties"] == pytest.approx(29.5, abs=0.1)
    assert lau["Pacific Rim Bank"] == pytest.approx(17.6, abs=0.1)
    hidden = [
        signal
        for signal in signals_of(context, "lookthrough_concentration")
        if signal.threshold["hidden_exposure"]
    ]
    assert {signal.client_id for signal in hidden} == {"CL-0015", "CL-0019"}
    assert all(signal.severity == "low" for signal in hidden)
    unknown = [
        signal
        for signal in signals_of(context, "lookthrough_unavailable")
        if signal.threshold["instrument_id"] == "SYN-SP-0506"
    ]
    assert unknown
    assert all(signal.severity == "low" for signal in unknown)
    assert all("unscreenable" in signal.threshold["disclosure"] for signal in unknown)
    for signal in unknown:
        assert "instruments:SYN-SP-0506" in signal.evidence_ids
    accumulator = facts_of(context, "CL-0014", "concentration.accumulator_below_strike_pct")[0]
    assert accumulator.value == pytest.approx(18.0232558)
    assert "remaining accumulation notional" in accumulator.inputs["action"]


def test_all_risk_references_resolve_and_exposure_denominators_are_cited(reviewed_context):
    context = reviewed_context
    for client_id, facts in context.facts.items():
        fact_ids = {fact.id for fact in facts}
        household = context.latest.loc[context.latest["client_id"].eq(client_id)]
        denominator_ids = set(context.holding_evidence(household))
        for fact in facts:
            assert set(fact.evidence_ids) <= context.source_evidence_ids
            if fact.kind in {
                "concentration.lookthrough_pct",
                "event.channel_exposure_pct",
                "currency.non_base_pct",
                "concentration.unscreenable_product_pct",
            }:
                assert denominator_ids <= set(fact.evidence_ids)
        for signal in context.signals[client_id]:
            assert set(signal.fact_ids) <= fact_ids
            assert set(signal.evidence_ids) <= context.source_evidence_ids


def test_fragile_cure_is_market_recovery_without_repayment(reviewed_context):
    signals = signals_of(reviewed_context, "collateral_stress")
    hartono = next(signal for signal in signals if signal.client_id == "CL-0001")
    assert hartono.threshold["fragile_cure"]
    assert hartono.threshold["cure_without_drawn_reduction"]
    assert hartono.threshold["breach_dates"] == ["2025-12-31", "2026-02-27"]
    assert any(identifier.startswith("event_log:") for identifier in hartono.evidence_ids)
    recovery = facts_of(reviewed_context, "CL-0001", "collateral.unresolved_recovery_share_pct")[0]
    assert recovery.value == pytest.approx(99.488154, abs=0.001)
    lau = facts_of(reviewed_context, "CL-0014", "collateral.consecutive_increases")[0]
    assert lau.value == 3
    context = make_context()
    facility_mask = context.tables["credit_facilities"]["facility_id"].eq("CF-0005")
    context.tables["credit_facilities"].loc[facility_mask, "drawn_2026-08-26"] -= 100_000
    _RiskEngine(context).collateral()
    hartono_facts = facts_of(context, "CL-0001", "collateral.ltv_pct")
    assert not hartono_facts[0].inputs["fragile_cure"]


def test_currency_qualifiers_and_income_aware_suitability(reviewed_context):
    context = reviewed_context
    currency = signals_of(context, "currency_mismatch")
    assert len(currency) == 7
    assert {signal.client_id for signal in currency if signal.severity == "high"} == {
        "CL-0005",
        "CL-0008",
        "CL-0014",
        "CL-0016",
    }
    suitability = signals_of(context, "suitability_drift")
    assert {signal.client_id for signal in suitability} == {"CL-0004", "CL-0012"}
    for signal in suitability:
        assert signal.threshold["income_received_base"] > 1_000_000
        assert "not total return" in signal.threshold["disclosure"]
        assert any(identifier.startswith("transactions:") for identifier in signal.evidence_ids)
    context = make_context()
    compute_performance(context)
    context.income_summary.loc["CL-0012", "income_base"] = float("nan")
    _RiskEngine(context).suitability()
    assert "CL-0012" not in {
        signal.client_id for signal in signals_of(context, "suitability_drift")
    }


def test_event_directions_and_reviewed_business_overlap(reviewed_context):
    signals = signals_of(reviewed_context, "event_exposure")
    assert signals
    assert {signal.client_id for signal in signals if signal.severity == "high"} == {
        "CL-0001",
        "CL-0002",
        "CL-0019",
    }
    for signal in signals:
        assert signal.threshold["direction"]
        assert signal.threshold["event_evidence_id"] in signal.evidence_ids
        assert signal.threshold["mapping_version"] == "phase-a-rm-review-v1"
        assert "pending" in signal.threshold["mapping_review_status"].lower() or (
            "required" in signal.threshold["mapping_review_status"].lower()
        )
    hartono = next(
        signal
        for signal in signals
        if signal.client_id == "CL-0001" and signal.threshold["channel"] == "energy"
    )
    assert "reopening" in hartono.threshold["direction"]
    assert {"rm_notes:N-001", "rm_notes:N-002"} <= set(hartono.evidence_ids)


def set_two_position_household(context, client_id, first_id, second_id, first_value):
    selected = context.latest.loc[
        context.latest["client_id"].eq(client_id)
        & context.latest["instrument_id"].isin([first_id, second_id])
    ].copy()
    assert len(selected) == 2
    selected.loc[selected["instrument_id"].eq(first_id), "market_value_usd"] = first_value
    selected.loc[selected["instrument_id"].eq(second_id), "market_value_usd"] = 100 - first_value
    context.latest = selected
    context.holdings = selected
    context.tables["holdings"] = selected


@pytest.mark.parametrize("weight,expected", [(15.0, False), (15.001, True)])
def test_event_threshold_is_strict(weight, expected):
    context = make_context()
    set_two_position_household(context, "CL-0015", "SYN-SP-0501", "SYN-CA-0601", weight)
    _RiskEngine(context).events()
    triggered = [
        signal
        for signal in signals_of(context, "event_exposure")
        if signal.threshold["channel"] == "technology"
    ]
    assert bool(triggered) is expected


@pytest.mark.parametrize("weight,expected", [(40.0, False), (40.001, True)])
def test_currency_threshold_is_strict(weight, expected):
    context = make_context()
    household = context.latest.loc[context.latest["client_id"].eq("CL-0005")]
    first_id = household.loc[household["instrument_ccy"].eq("USD"), "instrument_id"].iloc[0]
    second_id = household.loc[household["instrument_ccy"].eq("SGD"), "instrument_id"].iloc[0]
    set_two_position_household(context, "CL-0005", first_id, second_id, weight)
    _RiskEngine(context).currency()
    assert bool(signals_of(context, "currency_mismatch")) is expected


def test_hidden_exposure_fires_at_exactly_ten_percent():
    context = make_context()
    set_two_position_household(context, "CL-0015", "SYN-SP-0501", "SYN-CA-0601", 10.0)
    _RiskEngine(context).concentration()
    signals = signals_of(context, "lookthrough_concentration")
    assert any(
        signal.threshold["hidden_exposure"] and signal.severity == "low" for signal in signals
    )


def test_historical_maps_and_future_notes_are_not_used():
    context = make_context(date(2026, 3, 31))
    compute_performance(context)
    compute_risk(context)
    assert not context.reference_maps
    assert not signals_of(context, "event_exposure")
    for facts in context.facts.values():
        for fact in facts:
            assert "rm_notes:N-026" not in fact.evidence_ids
            if "snapshot_date" in fact.inputs:
                assert fact.inputs["snapshot_date"] <= "2026-03-31"
            assert not fact.inputs.get("fragile_cure", False)
    context = make_context(date(2026, 9, 5))
    compute_performance(context)
    compute_risk(context)
    for fact in facts_of(context, "CL-0014", "collateral.ltv_pct"):
        assert fact.as_of == date(2026, 9, 5)
        assert fact.inputs["snapshot_date"] == "2026-08-26"


def test_unmapped_event_is_disclosed_without_unsupported_claim():
    context = make_context()
    event = context.tables["event_log"].iloc[0].copy()
    event["primary_transmission"] = "Unreviewed channel"
    context.tables["event_log"] = pd.DataFrame([event])
    context.source_evidence_ids.add(evidence_id("event_log", event))
    _RiskEngine(context).events()
    assert not signals_of(context, "event_exposure")
    assert any("Unmapped event transmission" in issue for issue in context.context_issues)
