import shutil

import pandas as pd

from app.pipeline.features import legacy_analytics
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import DEFAULT_SOURCE_DIR, run_pipeline


def test_missing_fx_warns_and_discloses_unavailable_legacy_facts_without_blocking(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(DEFAULT_SOURCE_DIR, source, ignore=shutil.ignore_patterns("generated"))
    market = pd.read_csv(source / "market_context.csv")
    market = market[~((market["snapshot_date"] == "2026-08-26") & (market["category"] == "FX"))]
    market.to_csv(source / "market_context.csv", index=False)
    run = run_pipeline(
        source_dir=source, curated_dir=tmp_path / "curated", analytics=legacy_analytics
    )
    store = ArtifactStore(tmp_path / "curated")
    assert len(run.client_ids) == 20
    assert any("FX" in issue for issue in run.context_issues)
    assert store.load_fact_bundle("CL-0003").facts
    assert not store.load_fact_bundle("CL-0006").facts
    report = store.load_data_quality_report()
    assert not report.has_errors
    assert any(finding.code == "MISSING_FX_PATH" for finding in report.findings)


def test_adapter_keeps_source_and_converted_currencies_distinct(tmp_path):
    run_pipeline(curated_dir=tmp_path, analytics=legacy_analytics)
    facts = {
        fact.id.rsplit(":", 1)[-1]: fact
        for fact in ArtifactStore(tmp_path).load_fact_bundle("CL-0006").facts
        if ":deadline:" in fact.id
    }
    assert facts["amount"].currency == "USD"
    assert facts["amount_in_portfolio_currency"].currency == "SGD"
    assert facts["daily_liquid"].currency == "SGD"
    assert facts["days"].currency is None
    assert facts["coverage_pct"].currency is None
    assert facts["amount"].unit == "currency"
