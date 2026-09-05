import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.analytics.facts import fact_engine
from app.analytics.scoring import build_priority
from app.pipeline import SourceValidationError, evidence_id, load_sources

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AS_OF = date(2026, 8, 26)


@pytest.fixture(scope="module")
def sources() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    return load_sources(DATA, as_of=AS_OF)


@pytest.fixture(scope="module")
def computed(
    sources: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    tables, _notes = sources
    return fact_engine(tables, AS_OF)


def _fact(facts: dict[str, list[dict[str, Any]]], client_id: str, key: str) -> dict[str, Any]:
    return next(fact for fact in facts[client_id] if fact["id"] == f"{client_id}:fact:{key}")


def test_sources_load_and_validate(
    sources: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> None:
    tables, notes = sources

    assert set(tables) == {
        "clients",
        "credit_facilities",
        "event_log",
        "holdings",
        "mandates",
        "market_context",
        "planned_cash_needs",
        "portfolios",
    }
    assert len(tables["clients"]) == 20
    assert notes
    assert all({"note_id", "client_id", "note"} <= set(note) for note in notes)


def test_validation_aggregates_multiple_source_errors(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    clients = pd.read_csv(source / "clients.csv").drop(columns=["client_name"])
    clients.to_csv(source / "clients.csv", index=False)
    holdings = pd.read_csv(source / "holdings.csv").drop(columns=["asset_class"])
    holdings.to_csv(source / "holdings.csv", index=False)

    with pytest.raises(SourceValidationError) as caught:
        load_sources(source, as_of=AS_OF)

    diagnostics = caught.value.diagnostics
    assert {(item.file, item.field) for item in diagnostics} >= {
        ("clients.csv", "client_name"),
        ("holdings.csv", "asset_class"),
    }


def test_missing_fx_quote_is_a_source_diagnostic(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    market = pd.read_csv(source / "market_context.csv")
    current_quote = (market["snapshot_date"] == AS_OF.isoformat()) & (
        market["series_id"] == "USDSGD"
    )
    market = market[~current_quote]
    market.to_csv(source / "market_context.csv", index=False)

    with pytest.raises(SourceValidationError) as caught:
        load_sources(source, as_of=AS_OF)

    assert any(
        item.code == "missing_fx_quote" and "SGD" in item.message
        for item in caught.value.diagnostics
    )


def test_duplicate_event_identity_is_a_source_diagnostic(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    events = pd.read_csv(source / "event_log.csv")
    events = pd.concat([events, events.iloc[[0]]], ignore_index=True)
    events.to_csv(source / "event_log.csv", index=False)

    with pytest.raises(SourceValidationError) as caught:
        load_sources(source, as_of=AS_OF)

    assert any(
        item.file == "event_log.csv" and item.code == "duplicate_identifier"
        for item in caught.value.diagnostics
    )


def test_margarethe_mandate_fact_is_equity_71_5_against_30(
    computed: tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]],
) -> None:
    facts, _evidence = computed
    fact = _fact(facts, "CL-0003", "mandate-gap")

    assert fact["what"] == "Equity is 71.5% against a 30% maximum."
    assert fact["numbers"]["asset_class"] == "Equity"
    assert fact["numbers"]["actual_pct"] == 71.5
    assert fact["numbers"]["limit_pct"] == 30
    assert fact["numbers"]["gap_pct"] == 41.5
    assert fact["source_rows"]


def test_margarethe_priority_components_are_unchanged(
    computed: tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]],
) -> None:
    facts, _evidence = computed
    ranking = sorted(
        (build_priority(client_id, client_facts) for client_id, client_facts in facts.items()),
        key=lambda item: item["score"],
        reverse=True,
    )

    assert len(ranking) == 20
    assert ranking[0]["client_id"] == "CL-0003"
    assert ranking[0]["components"] == {"gap": 93, "deadline": 91, "consequence": 100}
    assert ranking[0]["urgency"] == "now"


def test_cross_currency_cash_coverage_uses_as_of_fx(
    computed: tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]],
) -> None:
    facts, _evidence = computed
    deadline = _fact(facts, "CL-0006", "deadline")

    assert deadline["numbers"]["amount_in_portfolio_currency"] == 6_760_000
    assert deadline["numbers"]["portfolio_currency"] == "SGD"
    assert deadline["numbers"]["coverage_pct"] == 250.2
    assert "market_context:2026-08-26:USDSGD" in deadline["source_rows"]


def test_every_fact_citation_resolves_to_an_existing_source_file(
    computed: tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]],
) -> None:
    facts, evidence = computed

    for client_facts in facts.values():
        for fact in client_facts:
            for citation in [*fact["source_rows"], *fact["event_ids"]]:
                entry = evidence[citation]
                assert entry["id"] == citation
                assert (ROOT / entry["source"]).is_file(), entry["source"]

    mandate = _fact(facts, "CL-0003", "mandate-gap")
    resolved = [evidence[citation] for citation in mandate["source_rows"]]
    assert any(entry["source"] == "data/mandates.csv" for entry in resolved)
    assert any(entry["source"] == "data/holdings.csv" for entry in resolved)


def test_market_evidence_ids_use_series_id() -> None:
    frame = pd.read_csv(DATA / "market_context.csv")
    current_quote = (frame["snapshot_date"] == AS_OF.isoformat()) & (frame["series_id"] == "USDSGD")
    row = frame[current_quote].iloc[0]

    assert evidence_id("market_context", row) == "market_context:2026-08-26:USDSGD"


def test_pipeline_cli_runs_without_writing_files(tmp_path) -> None:
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    before = sorted(path.relative_to(source) for path in source.rglob("*"))

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.pipeline",
            "run",
            "--source-dir",
            str(source),
            "--as-of",
            AS_OF.isoformat(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "clients: 20" in completed.stdout
    assert "CL-0003:fact:mandate-gap" in completed.stdout
    assert sorted(path.relative_to(source) for path in source.rglob("*")) == before
