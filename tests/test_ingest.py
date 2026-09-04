from datetime import date
from pathlib import Path

from app.pipeline.stages.ingest import ingest_sources

DATA = Path(__file__).parents[1] / "data"
AS_OF = date(2026, 8, 26)


def test_ingest_retains_all_twelve_sources_and_future_rows():
    sources = ingest_sources(DATA, as_of=date(2026, 1, 1))
    assert len(sources.tables) == 11
    assert len(sources.tables["holdings"]) == 1015
    assert len(sources.notes) == 28
    assert sources.tables["holdings"]["market_value_base"].dtype.kind == "f"
    assert sources.tables["holdings"]["snapshot_date"].max() == "2026-08-26"


def test_warning_report_resolves_evidence_and_never_blocks():
    from app.pipeline.stages.validate import source_evidence, validate_sources

    sources = ingest_sources(DATA, as_of=AS_OF)
    report = validate_sources(sources)
    assert not report.has_errors
    assert {"LAGGED_VALUATION", "MULTI_PORTFOLIO_CLIENT"} <= {f.code for f in report.findings}
    evidence = source_evidence(sources)
    assert all(e in evidence.entries for f in report.findings for e in f.evidence_ids)


def test_mutated_warning_records_remain_available():
    import pandas as pd

    from app.pipeline.stages.validate import source_evidence, validate_sources

    sources = ingest_sources(DATA, as_of=AS_OF)
    sources.notes[0]["client_id"] = "CL-UNKNOWN"
    sources.tables["portfolios"].loc[0, "mandate_code"] = "UNKNOWN"
    events = sources.tables["event_log"]
    sources.tables["event_log"] = pd.concat([events, events.iloc[[0]]], ignore_index=True)
    sources.tables["market_context"] = sources.tables["market_context"].loc[
        sources.tables["market_context"]["series_id"] != "EURUSD"
    ]
    report = validate_sources(sources)
    assert {
        "NOTE_UNKNOWN_CLIENT",
        "DUPLICATE_EVENT",
        "MISSING_FX_PATH",
        "MANDATE_NOT_MEASURED",
    } <= {f.code for f in report.findings}
    assert len(sources.tables["event_log"]) == 17
    evidence = source_evidence(sources)
    assert all(e in evidence.entries for f in report.findings for e in f.evidence_ids)


def test_missing_file_and_malformed_values_block_publication(tmp_path):
    import shutil

    import pytest

    from app.pipeline.stages.validate import QualityValidationError, validate_sources

    shutil.copytree(DATA, tmp_path, dirs_exist_ok=True)
    (tmp_path / "instruments.csv").unlink()
    holdings = tmp_path / "holdings.csv"
    holdings.write_text(holdings.read_text().replace("8452080.0", "not-a-number", 1))
    sources = ingest_sources(tmp_path, as_of=AS_OF)
    with pytest.raises(QualityValidationError) as caught:
        validate_sources(sources)
    assert caught.value.report.has_errors
    assert {"missing_file", "invalid_number"} <= {d.code for d in caught.value.diagnostics}
    assert len(sources.tables["holdings"]) == 1015


def test_broken_instrument_key_and_note_date_are_structural_errors():
    import pytest

    from app.pipeline.stages.validate import QualityValidationError, validate_sources

    sources = ingest_sources(DATA, as_of=AS_OF)
    sources.tables["holdings"].loc[0, "instrument_id"] = "MISSING"
    sources.notes[0]["note_date"] = "yesterday"
    with pytest.raises(QualityValidationError) as caught:
        validate_sources(sources)
    assert {"orphan_reference", "invalid_date"} <= {d.code for d in caught.value.diagnostics}
