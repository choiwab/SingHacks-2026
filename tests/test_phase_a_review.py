"""Independent financial-methodology checks against the reviewed Phase A specification."""

import math
from datetime import date
from pathlib import Path

import pytest

from app.analytics.phase_a import PhaseAContext, phase_a_analytics
from app.analytics.phase_a_funding import compute_funding
from app.analytics.phase_a_performance import compute_performance
from app.analytics.phase_a_quality import phase_a_quality_findings
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import run_pipeline
from app.pipeline.stages.clean import clean_sources
from app.pipeline.stages.ingest import ingest_sources

DATA = Path(__file__).resolve().parents[1] / "data"


def review_context(as_of=date(2026, 8, 26)):
    sources = ingest_sources(DATA, as_of=as_of)
    cleaned = clean_sources(sources.tables, sources.notes, as_of=as_of)
    return PhaseAContext(cleaned, "independent-methodology-review")


@pytest.fixture(scope="module")
def reviewed_publication(tmp_path_factory):
    destination = tmp_path_factory.mktemp("reviewed-phase-a")
    manifest = run_pipeline(curated_dir=destination)
    return ArtifactStore(destination), manifest


def require_finite_numbers(value):
    if isinstance(value, dict):
        for item in value.values():
            require_finite_numbers(item)
    elif isinstance(value, list):
        for item in value:
            require_finite_numbers(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_all_published_numbers_are_finite_and_all_references_resolve(reviewed_publication):
    store, manifest = reviewed_publication
    evidence = store.load_evidence_map(run_id=manifest.run_id)
    require_finite_numbers(evidence.model_dump(mode="json"))
    for client_id in manifest.client_ids:
        facts = store.load_fact_bundle(client_id).facts
        fact_ids = {fact.id for fact in facts}
        signals = store.load_signal_set(client_id).signals
        for item in [*facts, *signals]:
            require_finite_numbers(item.model_dump(mode="json"))
            assert item.evidence_ids
            assert set(item.evidence_ids) <= evidence.entries.keys()
        for signal in signals:
            assert set(signal.fact_ids) <= fact_ids
    for finding in store.load_data_quality_report().findings:
        if finding.code.startswith("PHASE_A_"):
            assert finding.evidence_ids
        assert set(finding.evidence_ids) <= evidence.entries.keys()


def test_material_source_limitations_survive_publication(reviewed_publication):
    store, _ = reviewed_publication
    findings = store.load_data_quality_report().findings
    by_code = {finding.code: finding for finding in findings}
    stale = by_code["PHASE_A_MATERIAL_STALE_VALUATION"]
    assert stale.client_id == "CL-0002"
    assert "High materiality" in stale.message
    assert "68.35%" in stale.message
    assert "2025-09-30" in stale.message
    transfer = by_code["PHASE_A_TRANSFER_TAX_BASIS_UNVERIFIED"]
    assert transfer.portfolio_id == "PF-0005"
    assert "inherited" in transfer.message
    assert "tax-lot history" in transfer.message
    assert "before disposal-tax advice" in transfer.message
    assert any(reference.startswith("transactions:") for reference in transfer.evidence_ids)
    facility = by_code["PHASE_A_FACILITY_ACTIVITY_UNRECONCILED"]
    assert facility.client_id == "CL-0014"
    assert "2,000,000.00 HKD unexplained" in facility.message
    assert {"credit_facilities:CF-0002", "transactions:TXN-0013"} <= set(facility.evidence_ids)
    assert "PHASE_A_MISSING_COST_BASIS" in by_code
    assert "PHASE_A_PURCHASE_BASIS_MISMATCH" in by_code
    assert "PHASE_A_LEDGER_UNRECONCILED" in by_code
    assert all(finding.severity == "warning" for finding in findings)


@pytest.mark.parametrize("missing_client", [None, "CL-0012"])
def test_missing_ledger_does_not_establish_zero_income_or_fees(missing_client):
    context = review_context()
    transactions = context.tables["transactions"]
    context.tables["transactions"] = (
        transactions.iloc[:0].copy()
        if missing_client is None
        else transactions.loc[transactions["client_id"].ne(missing_client)].copy()
    )
    compute_performance(context)
    unavailable = list(context.client_names) if missing_client is None else [missing_client]
    for client_id in unavailable:
        assert context.income_summary.loc[client_id].isna().all()
        assert not any(
            fact.kind.startswith(("income.", "fees.")) for fact in context.facts[client_id]
        )
    assert any("unavailable" in issue.lower() for issue in context.context_issues)
    findings = phase_a_quality_findings(context.sources)
    assert any(
        finding.code == "PHASE_A_LEDGER_UNAVAILABLE" and finding.client_id == missing_client
        for finding in findings
    )
    if missing_client is not None:
        assert any(fact.kind == "income.received_usd" for fact in context.facts["CL-0004"])


def test_historical_called_to_date_is_not_reused_as_historical_obligations():
    context = review_context(date(2026, 6, 30))
    compute_funding(context)
    clients_with_commitments = set(context.tables["commitments"]["client_id"])
    for client_id in clients_with_commitments:
        kinds = {fact.kind for fact in context.facts[client_id]}
        assert "funding.cash_usd" in kinds
        assert "funding.obligations_usd" not in kinds
        assert "funding.cash_cover_x" not in kinds
        assert not any(signal.kind == "funding_gap" for signal in context.signals[client_id])
        assert any(
            client_id in issue and "historical uncalled balances unavailable" in issue
            for issue in context.context_issues
        )


def test_earlier_as_of_uses_actual_snapshot_and_withholds_future_mappings():
    context = review_context(date(2026, 3, 15))
    artifacts = phase_a_analytics(context.sources, context.run_id)
    assert context.snapshot == "2026-02-27"
    assert context.reference_maps == {}
    for bundle in artifacts.facts.values():
        for fact in bundle.facts:
            if "snapshot" in fact.inputs:
                assert fact.inputs["snapshot"] <= "2026-02-27"
            for reference in fact.evidence_ids:
                if reference.startswith("rm_notes:"):
                    assert reference.removeprefix("rm_notes:") in context.notes
    assert not any(
        signal.kind == "event_exposure"
        for bundle in artifacts.signals.values()
        for signal in bundle.signals
    )
    assert any("not effective" in issue for issue in artifacts.context_issues)


def test_reviewed_cash_covers_preserve_deadline_and_deduplication_meaning(reviewed_publication):
    store, _ = reviewed_publication
    expected = {
        "CL-0003": (0.4591741166, 5.2748695486, 3_712_800),
        "CL-0006": (0.25887574, 1.56362152375, 8_000_000),
        "CL-0017": (0.32297005988, 3.2709568862, 16_700_000),
    }
    for client_id, (cash_cover, daily_cover, obligations) in expected.items():
        facts = {fact.kind: fact for fact in store.load_fact_bundle(client_id).facts}
        assert facts["funding.cash_cover_x"].value == pytest.approx(cash_cover)
        assert facts["funding.daily_cover_x"].value == pytest.approx(daily_cover)
        assert facts["funding.obligations_usd"].value == pytest.approx(obligations)
        signal = next(
            signal
            for signal in store.load_signal_set(client_id).signals
            if signal.kind == "funding_gap"
        )
        assert signal.severity == "high"
        assert not signal.threshold["escalate_12m"]
        assert signal.threshold["escalate_near_term"]
    margarethe = {fact.kind: fact for fact in store.load_fact_bundle("CL-0003").facts}
    assert margarethe["funding.scenario.post_withdrawal_equity_pct"].value == pytest.approx(
        65.72318
    )
    assert margarethe["funding.scenario.further_equity_reallocation_base"].value == pytest.approx(
        6_041_645.883
    )


def test_issuer_screen_preserves_missing_basket_and_pending_human_approval(reviewed_publication):
    store, manifest = reviewed_publication
    lau = {
        fact.inputs["issuer"]: fact.value
        for fact in store.load_fact_bundle("CL-0014").facts
        if fact.kind == "concentration.lookthrough_pct"
    }
    assert lau["Golden Harbour Properties"] == pytest.approx(29.5, abs=0.1)
    assert lau["Pacific Rim Bank"] == pytest.approx(17.6, abs=0.1)
    assert any("human RM approval" in issue for issue in manifest.context_issues)
    unknown = [
        signal
        for signal in store.load_signal_set("CL-0003").signals
        if signal.kind == "lookthrough_unavailable"
        and signal.threshold["instrument_id"] == "SYN-SP-0506"
    ]
    assert unknown
    assert "unscreenable" in unknown[0].threshold["disclosure"]
