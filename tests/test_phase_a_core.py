"""Reviewed performance, Mandate and funding arithmetic and historical boundaries."""

import math
from datetime import date
from pathlib import Path

import pytest

from app.analytics.phase_a import PhaseAContext
from app.analytics.phase_a_funding import compute_funding, funding_severity
from app.analytics.phase_a_mandates import band_gap, compute_mandates
from app.analytics.phase_a_performance import compute_performance
from app.pipeline.stages.clean import clean_sources
from app.pipeline.stages.ingest import ingest_sources

DATA = Path(__file__).resolve().parents[1] / "data"


def make_context(as_of=date(2026, 8, 26)):
    sources = ingest_sources(DATA, as_of=as_of)
    return PhaseAContext(clean_sources(sources.tables, sources.notes, as_of=as_of), "core-test")


@pytest.fixture(scope="module")
def reviewed_context():
    context = make_context()
    compute_performance(context)
    compute_mandates(context)
    compute_funding(context)
    return context


def facts_of(context, client_id, kind):
    return [fact for fact in context.facts[client_id] if fact.kind == kind]


def signals_of(context, kind):
    return [
        signal for signals in context.signals.values() for signal in signals if signal.kind == kind
    ]


@pytest.mark.parametrize(
    "client_id,expected",
    [
        ("CL-0001", 18.960599),
        ("CL-0019", 9.673705),
        ("CL-0015", 9.170752),
        ("CL-0013", 10.160919),
    ],
)
def test_same_store_returns_exclude_added_positions(reviewed_context, client_id, expected):
    fact = facts_of(reviewed_context, client_id, "performance.same_store_return_base_pct")[0]
    assert fact.value == pytest.approx(expected, abs=0.000001)
    assert "not reconciled total return" in fact.inputs["disclosure"]


def test_added_cost_and_own_move_reconcile_to_reported_value_change(reviewed_context):
    context = reviewed_context
    totals = {}
    for client_id, facts in context.facts.items():
        values = {fact.kind: fact.value for fact in facts if fact.kind.startswith("performance.")}
        opening = context.holdings.loc[
            context.holdings["client_id"].eq(client_id)
            & context.holdings["snapshot_date"].eq(context.baseline),
            "market_value_usd",
        ].sum()
        ending = context.latest.loc[
            context.latest["client_id"].eq(client_id), "market_value_usd"
        ].sum()
        components = [
            "performance.starting_price_effect_usd",
            "performance.starting_fx_effect_usd",
            "performance.new_position_cost_usd",
            "performance.post_purchase_move_usd",
        ]
        assert sum(values[kind] for kind in components) == pytest.approx(ending - opening, abs=0.05)
        for kind in components:
            totals[kind] = totals.get(kind, 0) + values[kind]
    assert totals["performance.new_position_cost_usd"] == pytest.approx(15_335_545.20, abs=0.01)
    assert totals["performance.post_purchase_move_usd"] == pytest.approx(-680_254.04, abs=0.01)


def test_income_fees_and_financing_remain_separate(reviewed_context):
    income = facts_of(reviewed_context, "CL-0003", "income.received_base")[0]
    fees = facts_of(reviewed_context, "CL-0003", "fees.management_base")[0]
    financing = facts_of(reviewed_context, "CL-0001", "fees.financing_interest_base")[0]
    assert income.value == pytest.approx(331_538.37, abs=0.01)
    assert fees.value == pytest.approx(55_079.26, abs=0.01)
    assert financing.value == pytest.approx(216_000)
    assert "Not reconciled to positions" in income.inputs["disclosure"]
    assert any(identifier.startswith("transactions:") for identifier in income.evidence_ids)


def test_mandate_counts_threshold_facts_and_binding_exclusions(reviewed_context):
    context = reviewed_context
    bands = signals_of(context, "mandate_band_breach")
    positions = signals_of(context, "mandate_single_position_breach")
    exclusions = signals_of(context, "mandate_exclusion_breach")
    assert len(bands) == 14
    assert len({signal.client_id for signal in bands}) == 9
    assert len(positions) == 13
    assert len(exclusions) == 2
    exclusion_weights = [
        fact.value
        for facts in context.facts.values()
        for fact in facts
        if fact.kind == "mandate.excluded_position_pct"
    ]
    assert sum(exclusion_weights) == pytest.approx(21.30, abs=0.01)
    for signal in bands + positions:
        linked = {
            fact.kind: fact
            for fact in context.facts[signal.client_id]
            if fact.id in signal.fact_ids
        }
        if signal.kind == "mandate_band_breach":
            gap = linked["mandate.band_gap_pp"].value
            kind = "mandate.maximum_pct" if gap > 0 else "mandate.minimum_pct"
            assert linked["mandate.allocation_pct"].value - linked[kind].value == pytest.approx(gap)
        else:
            assert linked["mandate.single_position_pct"].value - linked[
                "mandate.single_position_limit_pct"
            ].value == pytest.approx(linked["mandate.single_position_gap_pp"].value)
    assert all(signal.threshold["documentation_failure"] for signal in exclusions)
    assert band_gap(30, 10, 30) == 0
    assert band_gap(10, 10, 30) == 0


def test_funding_deduplicates_calls_and_escalates_daily_cash_deadlines(reviewed_context):
    context = reviewed_context
    for client_id, expected, cash_cover, daily_cover in [
        ("CL-0017", 16_700_000, 0.32, 3.27),
        ("CL-0006", 8_000_000, 0.26, 1.56),
    ]:
        assert facts_of(context, client_id, "funding.obligations_usd")[0].value == expected
        assert facts_of(context, client_id, "funding.cash_cover_x")[0].value == pytest.approx(
            cash_cover, abs=0.005
        )
        assert facts_of(context, client_id, "funding.daily_cover_x")[0].value == pytest.approx(
            daily_cover, abs=0.005
        )
    fong = facts_of(context, "CL-0017", "funding.obligations_usd")[0]
    assert {row["obligation_id"] for row in fong.inputs["obligations"]} == {
        "CN-015",
        "COM-001",
        "COM-002",
    }
    margarethe = next(
        signal for signal in signals_of(context, "funding_gap") if signal.client_id == "CL-0003"
    )
    assert margarethe.severity == "high"
    assert margarethe.threshold["escalate_near_term"]
    assert not margarethe.threshold["escalate_12m"]
    assert funding_severity(1, 1.5, 100, 100) == "none"
    assert funding_severity(0.9, 1.5, 100, 100) == "medium"
    assert funding_severity(0.9, 1.499, 100, 100) == "high"
    assert funding_severity(2, 3, 100, 99) == "high"


def test_conditional_sale_and_zero_obligations_do_not_become_resources(reviewed_context):
    context = reviewed_context
    assert facts_of(context, "CL-0002", "funding.obligations_usd")[0].value == 2_000_000
    contingent = facts_of(context, "CL-0002", "funding.contingent_need_usd")[0]
    assert contingent.value == 4_200_000
    assert contingent.inputs["excluded_from_baseline"]
    assert facts_of(context, "CL-0010", "funding.obligations_usd")[0].value == 0
    assert not facts_of(context, "CL-0010", "funding.cash_cover_x")


def test_withdrawal_scenario_preserves_external_payment_denominator(reviewed_context):
    context = reviewed_context
    scenario = {
        fact.kind.removeprefix("funding.scenario."): fact
        for fact in context.facts["CL-0003"]
        if fact.kind.startswith("funding.scenario.")
    }
    assert scenario["withdrawal_base"].value == 3_400_000
    assert scenario["post_withdrawal_total_base"].value == pytest.approx(16_912_395.29)
    assert scenario["post_withdrawal_equity_pct"].value == pytest.approx(65.723183, abs=0.000001)
    assert scenario["further_equity_reallocation_base"].value == pytest.approx(
        6_041_645.88, abs=0.01
    )
    assert scenario["post_reallocation_equity_pct"].value == pytest.approx(30)
    assert scenario["post_reallocation_fixed_income_pct"].value == pytest.approx(46.709208)
    signal = next(
        signal for signal in signals_of(context, "funding_gap") if signal.client_id == "CL-0003"
    )
    for fact in scenario.values():
        assert {"planned_cash_needs:CN-004", "rm_notes:N-005"} <= set(fact.evidence_ids)
        assert "not a trade instruction" in fact.inputs["disclosure"]
        assert fact.id in signal.fact_ids


def test_historical_calls_and_scenario_are_withheld_without_fabricated_zero():
    context = make_context(date(2026, 5, 29))
    compute_performance(context)
    compute_funding(context)
    assert not context.reference_maps
    for client_id in ["CL-0006", "CL-0009", "CL-0017", "CL-0020"]:
        assert facts_of(context, client_id, "funding.cash_usd")
        assert not facts_of(context, client_id, "funding.obligations_usd")
        assert not facts_of(context, client_id, "funding.uncalled_usd")
        assert not any(signal.kind == "funding_gap" for signal in context.signals[client_id])
    assert not any(fact.kind.startswith("funding.scenario.") for fact in context.facts["CL-0003"])
    assert any(
        "historical uncalled balances unavailable" in issue for issue in context.context_issues
    )


def test_all_values_are_finite_and_every_reference_resolves(reviewed_context):
    context = reviewed_context
    for client_id, facts in context.facts.items():
        identifiers = {fact.id for fact in facts}
        for fact in facts:
            assert math.isfinite(fact.value)
            assert fact.evidence_ids
            assert set(fact.evidence_ids) <= context.source_evidence_ids
        for signal in context.signals[client_id]:
            assert set(signal.fact_ids) <= identifiers
            assert set(signal.evidence_ids) <= context.source_evidence_ids


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_fact_emission_is_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        make_context().emit_fact("CL-0003", "invalid", value, evidence_ids=["clients:CL-0003"])
