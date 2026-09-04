import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.wealth_intelligence import MondayBriefProjection, ProjectionBuildError, build_monday_brief
from app.wealth_intelligence.models import ReviewRequest
from app.wealth_intelligence.reviews import ReviewLedger

DATA = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 8, 26)


def test_public_interface_returns_typed_projection() -> None:
    projection = build_monday_brief(DATA, as_of=AS_OF)

    assert isinstance(projection, MondayBriefProjection)
    assert projection.schema_version == 1
    assert projection.ranking[0].client_id == "CL-0003"
    assert all(fact.kind for facts in projection.facts.values() for fact in facts)


def test_cross_currency_cash_coverage_uses_as_of_fx() -> None:
    projection = build_monday_brief(DATA, as_of=AS_OF)
    deadline = next(fact for fact in projection.facts["CL-0006"] if fact.kind == "deadline")

    assert deadline.numbers.amount_in_portfolio_currency == 6_760_000
    assert deadline.numbers.portfolio_currency == "SGD"
    assert deadline.numbers.coverage_pct == 250.2
    assert "market_context:2026-08-26:USDSGD" in deadline.source_rows


def test_every_projection_reference_resolves() -> None:
    projection = build_monday_brief(DATA, as_of=AS_OF)
    evidence_ids = set(projection.evidence)
    fact_ids = {fact.id for facts in projection.facts.values() for fact in facts}

    for facts in projection.facts.values():
        for fact in facts:
            assert set(fact.source_rows + fact.event_ids) <= evidence_ids
    for pre_read in projection.pre_reads.values():
        cited = [
            *pre_read.what_changed,
            *pre_read.rules_money,
            pre_read.gap,
            pre_read.opening,
            pre_read.uncertainty,
            *pre_read.beliefs,
            *pre_read.workflow,
        ]
        assert all(set(item.citations) <= evidence_ids | fact_ids for item in cited)


def test_validation_aggregates_multiple_source_errors(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    clients = pd.read_csv(source / "clients.csv").drop(columns=["client_name"])
    clients.to_csv(source / "clients.csv", index=False)
    holdings = pd.read_csv(source / "holdings.csv").drop(columns=["asset_class"])
    holdings.to_csv(source / "holdings.csv", index=False)

    with pytest.raises(ProjectionBuildError) as caught:
        build_monday_brief(source, as_of=AS_OF)

    diagnostics = caught.value.diagnostics
    assert {(item.file, item.field) for item in diagnostics} >= {
        ("clients.csv", "client_name"),
        ("holdings.csv", "asset_class"),
    }


def test_missing_fx_quote_is_a_build_diagnostic(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    market = pd.read_csv(source / "market_context.csv")
    current_quote = (market["snapshot_date"] == AS_OF.isoformat()) & (
        market["series_id"] == "USDSGD"
    )
    market = market[~current_quote]
    market.to_csv(source / "market_context.csv", index=False)

    with pytest.raises(ProjectionBuildError) as caught:
        build_monday_brief(source, as_of=AS_OF)

    assert any(
        item.code == "missing_fx_quote" and "SGD" in item.message
        for item in caught.value.diagnostics
    )


def test_duplicate_event_identity_is_a_build_diagnostic(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    events = pd.read_csv(source / "event_log.csv")
    events = pd.concat([events, events.iloc[[0]]], ignore_index=True)
    events.to_csv(source / "event_log.csv", index=False)

    with pytest.raises(ProjectionBuildError) as caught:
        build_monday_brief(source, as_of=AS_OF)

    assert any(
        item.file == "event_log.csv" and item.code == "duplicate_identifier"
        for item in caught.value.diagnostics
    )


def test_market_evidence_ids_use_series_id() -> None:
    frame = pd.read_csv(DATA / "market_context.csv")
    current_quote = (frame["snapshot_date"] == AS_OF.isoformat()) & (frame["series_id"] == "USDSGD")
    row = frame[current_quote].iloc[0]

    from app.pipeline import _evidence_id

    assert _evidence_id("market_context", row) == "market_context:2026-08-26:USDSGD"


def test_review_ledger_accepts_concurrent_writes(tmp_path) -> None:
    ledger = ReviewLedger(tmp_path / "reviews.sqlite3")
    request = ReviewRequest(client_id="CL-0003", action="Edit", text="Reviewed")

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: ledger.append(request, rm="Priscilla Ong"), range(12)))

    assert len({record.review_id for record in records}) == 12
    assert len(ledger.list()) == 12


def test_legacy_import_is_transactional_and_idempotent(tmp_path) -> None:
    source = tmp_path / "review_log.json"
    source.write_text(
        json.dumps(
            [
                {
                    "client_id": "CL-0003",
                    "action": "Approve",
                    "text": "Looks good",
                    "rm": "Priscilla Ong",
                    "timestamp": "2026-08-26T01:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    ledger = ReviewLedger(":memory:")

    assert ledger.import_legacy_json(source) == 1
    assert ledger.import_legacy_json(source) == 0
    assert len(ledger.list()) == 1
    assert source.exists()
    ledger.close()
