from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.pipeline.schemas import Fact, FactBundle


def test_one_number_fact_roundtrips_with_provenance():
    fact = Fact(
        id="CL-0003:fact:equity_pct",
        client_id="CL-0003",
        kind="equity_pct",
        value=71.5,
        unit="percent",
        formula_id="allocation_pct",
        inputs={"market_values": [10, 20], "total": "CL-0003:fact:aum"},
        evidence_ids=["holdings:2026-08-26:PF-0003:EQ-001"],
        as_of=date(2026, 8, 26),
        confidence=1.0,
    )
    bundle = FactBundle(run_id="abc123", as_of=fact.as_of, client_id=fact.client_id, facts=[fact])
    assert FactBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert bundle.model_dump(mode="json")["facts"][0]["value"] == 71.5
    with pytest.raises(ValidationError):
        Fact.model_validate({**fact.model_dump(), "value": {"equity_pct": 71.5}})
    with pytest.raises(ValidationError):
        Fact.model_validate({**fact.model_dump(), "timestamp": "2026-08-26T00:00:00"})


def test_signal_quality_and_run_artifacts_roundtrip():
    from app.pipeline.schemas import (
        ChangeReport,
        DataQualityFinding,
        DataQualityReport,
        Evidence,
        EvidenceMap,
        FactChange,
        RunManifest,
        Signal,
        SignalChange,
        SignalSet,
    )

    day = date(2026, 8, 26)
    signal = Signal(
        id="s1",
        client_id="CL-0003",
        kind="mandate_breach",
        severity="high",
        priority_score=90,
        score_components={"breach": 90},
        threshold=30,
        fact_ids=["f1"],
        evidence_ids=["clients:CL-0003"],
        as_of=day,
    )
    evidence = Evidence(
        id="clients:CL-0003",
        kind="clients",
        title="Client",
        source="clients",
        record={"client_id": "CL-0003"},
        source_file="clients.csv",
        row_index=2,
        fields={"client_id": "CL-0003"},
    )
    finding = DataQualityFinding(
        code="MULTI_PORTFOLIO_CLIENT",
        severity="warning",
        client_id="CL-0003",
        evidence_ids=[evidence.id],
        message="Multiple",
    )
    report = DataQualityReport(as_of=day, run_id="r1", findings=[finding])
    artifacts = [
        signal,
        evidence,
        finding,
        SignalSet(as_of=day, run_id="r1", client_id="CL-0003", signals=[signal]),
        EvidenceMap(as_of=day, run_id="r1", entries={evidence.id: evidence}),
        report,
        ChangeReport(
            as_of=day,
            run_id="r1",
            client_id="CL-0003",
            processing_mode="incremental_update",
            prior_run_id="r0",
            fact_changes=[FactChange(fact_id="f1", change="changed", before=29.5, after=71.5)],
            signal_changes=[SignalChange(signal_id="s1", change="added", after="high")],
        ),
        RunManifest(
            as_of=day,
            run_id="r1",
            pipeline_version="1",
            git_sha="abc",
            source_hashes={"clients.csv": "sha"},
            client_ids=["CL-0003"],
            created_at=datetime(2026, 9, 5, tzinfo=UTC),
        ),
    ]
    for artifact in artifacts:
        assert type(artifact).model_validate_json(artifact.model_dump_json()) == artifact
        with pytest.raises(ValidationError):
            type(artifact).model_validate({**artifact.model_dump(), "unexpected": True})
    assert not report.has_errors
    assert report.warning_count == 1
    report.findings.append(DataQualityFinding(code="BROKEN_KEY", severity="error", message="Bad"))
    assert report.has_errors
    assert report.error_count == 1


def test_complete_curated_bundle_roundtrips_source_records():
    import csv
    import json
    from pathlib import Path

    from app.pipeline.schemas import (
        CashNeed,
        ClientProfile,
        Commitment,
        CreditFacility,
        CreditSnapshot,
        CuratedClientBundle,
        Holding,
        LiquidityPosition,
        MandateRule,
        Portfolio,
        RMNote,
    )

    source_dir = Path(__file__).resolve().parents[1] / "data"

    def rows(filename):
        with (source_dir / filename).open() as handle:
            return [
                {
                    k: (
                        None
                        if v == ""
                        and k
                        in {
                            "age",
                            "avg_cost_local",
                            "cost_basis_base",
                            "unrealised_pnl_base",
                            "unrealised_pnl_pct",
                        }
                        else v
                    )
                    for k, v in row.items()
                }
                for row in csv.DictReader(handle)
            ]

    client_id = "CL-0003"
    profile = ClientProfile.model_validate(
        next(r for r in rows("clients.csv") if r["client_id"] == client_id)
    )
    portfolios = []
    for row in rows("portfolios.csv"):
        if row["client_id"] == client_id:
            dated = {key[4:]: row.pop(key) for key in list(row) if key.startswith("aum_20")}
            portfolios.append(Portfolio.model_validate({**row, "aum_by_date": dated}))
    holdings = [
        Holding.model_validate(r) for r in rows("holdings.csv") if r["client_id"] == client_id
    ]
    mandates = [
        MandateRule.model_validate(r)
        for r in rows("mandates.csv")
        if r["mandate_code"] in {p.mandate_code for p in portfolios}
    ]
    cash_needs = [
        CashNeed.model_validate(r)
        for r in rows("planned_cash_needs.csv")
        if r["client_id"] == client_id
    ]
    commitments = [Commitment.model_validate(r) for r in rows("commitments.csv")]
    credit = []
    for row in rows("credit_facilities.csv"):
        snapshots = []
        for day in ("2025-12-31", "2026-02-27", "2026-03-31", "2026-06-30", "2026-08-26"):
            values = {
                key: row.pop(f"{key}_{day}")
                for key in (
                    "drawn",
                    "collateral_market_value",
                    "lending_value",
                    "ltv_pct",
                    "headroom",
                )
            }
            snapshots.append(CreditSnapshot.model_validate({"snapshot_date": day, **values}))
        credit.append(CreditFacility.model_validate({**row, "snapshots": snapshots}))
    notes = [
        RMNote(**n, evidence_id=f"rm_notes:{n['note_id']}")
        for n in json.loads((source_dir / "rm_notes.json").read_text())
        if n["client_id"] == client_id
    ]
    holding = holdings[0]
    liquidity = LiquidityPosition(
        snapshot_date=holding.snapshot_date,
        portfolio_id=holding.portfolio_id,
        instrument_id=holding.instrument_id,
        liquidity_tier=holding.liquidity_tier,
        market_value_base=holding.market_value_base,
        currency=holding.portfolio_ccy,
    )
    bundle = CuratedClientBundle(
        as_of=date(2026, 8, 26),
        run_id="r1",
        client_id=client_id,
        profile=profile,
        portfolios=portfolios,
        holdings=holdings,
        mandate_rules=mandates,
        liquidity=[liquidity],
        cash_needs=cash_needs,
        credit=[c for c in credit if c.client_id == client_id],
        commitments=[c for c in commitments if c.client_id == client_id],
        rm_notes=notes,
    )
    assert CuratedClientBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert len({h.snapshot_date for h in bundle.holdings}) == 5
    assert [n.note_id for n in bundle.rm_notes] == ["N-005", "N-006"]
    for nested in [
        profile,
        *portfolios,
        *holdings,
        *mandates,
        *cash_needs,
        *commitments,
        *credit,
        *credit[0].snapshots,
        *notes,
        liquidity,
    ]:
        assert type(nested).model_validate_json(nested.model_dump_json()) == nested
        with pytest.raises(ValidationError):
            type(nested).model_validate({**nested.model_dump(), "unknown": "ignored?"})
