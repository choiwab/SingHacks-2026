from datetime import date

import pandas as pd

from app.pipeline.stages.clean import clean_sources


def test_clean_removes_future_observations_but_keeps_known_future_cash_needs():
    tables = {
        "clients": pd.DataFrame(
            [{"client_id": "CL-0003", "kyc_review_due": "2026-11-30", "total_aum_usd": 123}]
        ),
        "portfolios": pd.DataFrame(
            [
                {
                    "portfolio_id": "PF-1",
                    "client_id": "CL-0003",
                    "inception_date": "2020-01-01",
                    "aum_2026-06-30": 100,
                    "aum_2026-08-26": 120,
                    "aum_usd_current": 120,
                }
            ]
        ),
        "holdings": pd.DataFrame(
            [
                {
                    "client_id": "CL-0003",
                    "snapshot_date": "2026-06-30",
                    "valuation_date": "2026-06-30",
                },
                {
                    "client_id": "CL-0003",
                    "snapshot_date": "2026-08-26",
                    "valuation_date": "2026-08-26",
                },
            ]
        ),
        "planned_cash_needs": pd.DataFrame([{"client_id": "CL-0003", "due_from": "2026-10-01"}]),
        "transactions": pd.DataFrame(
            [{"client_id": "CL-0003", "trade_date": "2026-06-29", "settlement_date": "2026-07-01"}]
        ),
    }
    notes = [
        {"client_id": "CL-0003", "note_date": "2026-08-24"},
        {"client_id": "CL-0003", "note_date": "2026-06-01"},
    ]
    cleaned = clean_sources(tables, notes, as_of=date(2026, 6, 30))
    assert len(cleaned.tables["holdings"]) == 1
    assert "aum_2026-08-26" not in cleaned.tables["portfolios"]
    assert "aum_usd_current" not in cleaned.tables["portfolios"]
    assert "total_aum_usd" not in cleaned.tables["clients"]
    assert cleaned.tables["transactions"].empty
    assert len(cleaned.notes) == 1
    assert cleaned.tables["planned_cash_needs"].iloc[0]["due_from"] == "2026-10-01"
    assert len(cleaned.clients["CL-0003"]["holdings"]) == 1
    assert len(tables["holdings"]) == 2


def test_historical_full_dataset_has_no_future_observations_or_dated_columns():
    import re
    from pathlib import Path

    from app.pipeline.stages.clean import OBSERVATION_DATES
    from app.pipeline.stages.ingest import ingest_sources

    as_of = date(2026, 6, 30)
    sources = ingest_sources(Path(__file__).parents[1] / "data", as_of=as_of)
    original = sources.tables["holdings"].copy(deep=True)
    cleaned = clean_sources(sources.tables, sources.notes, as_of=as_of)
    assert len(cleaned.clients) == 20
    for name, frame in cleaned.tables.items():
        for column in OBSERVATION_DATES.get(name, ()):
            assert all(value <= as_of.isoformat() for value in frame[column])
        for column in frame.columns:
            match = re.search(r"(\d{4}-\d{2}-\d{2})$", column)
            assert match is None or match[1] <= as_of.isoformat()
    assert all(note["note_date"] <= as_of.isoformat() for note in cleaned.notes)
    assert cleaned.tables["holdings"]["snapshot_date"].max() == "2026-06-30"
    assert "price_2026-08-26" not in cleaned.tables["instruments"]
    assert "drawn_2026-08-26" not in cleaned.tables["credit_facilities"]
    assert set(cleaned.tables["holdings"].index) <= set(original.index)
    pd.testing.assert_frame_equal(sources.tables["holdings"], original)


def test_analytics_hooks_receive_filtered_copies_and_run_in_declared_order():
    tables = {
        "clients": pd.DataFrame([{"client_id": "CL-0003"}]),
        "holdings": pd.DataFrame(
            [
                {"snapshot_date": "2026-08-26", "client_id": "CL-0003"},
                {"snapshot_date": "2026-06-30", "client_id": "CL-0003"},
            ]
        ),
    }
    calls = []

    def fx(frames, as_of):
        assert frames["holdings"]["snapshot_date"].tolist() == ["2026-06-30"]
        calls.append(("fx", as_of))
        frames["holdings"]["normalized"] = True
        return frames

    def bond(frames, as_of):
        assert frames["holdings"]["normalized"].all()
        calls.append(("bond", as_of))
        return frames

    def lookthrough(frames, as_of):
        calls.append(("lookthrough", as_of))
        return frames

    as_of = date(2026, 6, 30)
    cleaned = clean_sources(
        tables,
        [],
        as_of=as_of,
        normalize_fx=fx,
        normalize_bond_nominal=bond,
        look_through=lookthrough,
    )
    assert calls == [("fx", as_of), ("bond", as_of), ("lookthrough", as_of)]
    assert "normalized" in cleaned.clients["CL-0003"]["holdings"]
    assert "normalized" not in tables["holdings"]
