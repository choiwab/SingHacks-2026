import shutil

import pandas as pd

from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import DEFAULT_SOURCE_DIR, run_pipeline


def test_missing_fx_warns_and_discloses_unavailable_legacy_facts_without_blocking(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(DEFAULT_SOURCE_DIR, source, ignore=shutil.ignore_patterns("generated"))
    market = pd.read_csv(source / "market_context.csv")
    market = market[~((market["snapshot_date"] == "2026-08-26") & (market["category"] == "FX"))]
    market.to_csv(source / "market_context.csv", index=False)
    run = run_pipeline(source_dir=source, curated_dir=tmp_path / "curated")
    store = ArtifactStore(tmp_path / "curated")
    assert len(run.client_ids) == 20
    assert any("FX" in issue for issue in run.context_issues)
    assert store.load_fact_bundle("CL-0003").facts
    assert not store.load_fact_bundle("CL-0006").facts
    report = store.load_data_quality_report()
    assert not report.has_errors
    assert any(finding.code == "MISSING_FX_PATH" for finding in report.findings)
