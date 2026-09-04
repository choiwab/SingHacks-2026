"""Public ledger behavior, persistence, and migration coverage."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger


def add_run(ledger, run_id="seed", *, is_seed=True):
    return ledger.add_run(
        run_id=run_id,
        pipeline_version="1",
        as_of="2026-08-26",
        source_hashes={"clients.csv": "abc"},
        is_seed=is_seed,
    )


def add_brief(ledger, run_id="seed", **kwargs):
    return ledger.store_brief(
        client_id="CL-0003",
        run_id=run_id,
        body={"opening": {"text": "Review concentration"}},
        verification_report={"status": "verified", "claims": []},
        **kwargs,
    )


def test_run_registration_is_immutable_and_idempotent(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = ReviewLedger(path)
    seed = add_run(ledger)
    assert add_run(ledger) == seed
    with pytest.raises(ValueError, match="different metadata"):
        ledger.add_run(
            run_id="seed",
            pipeline_version="2",
            as_of="2026-08-26",
            source_hashes={},
        )
    update = add_run(ledger, "updated", is_seed=False)
    ledger.close()
    reopened = ReviewLedger(path)
    assert reopened.list_runs() == [seed, update]
    assert reopened.seed_run() == seed
    assert reopened.get_run("missing") is None


def test_brief_versions_preserve_original_body_and_verification(tmp_path):
    ledger = ReviewLedger(tmp_path / "ledger.sqlite3")
    add_run(ledger)
    first = add_brief(ledger)
    edited = ledger.store_brief(
        client_id="CL-0003",
        run_id="seed",
        body={"opening": {"text": "RM edit"}},
        verification_report={"status": "blocked"},
        origin="rm_edited",
        brief_version=2,
    )
    assert ledger.get_brief("CL-0003", "seed", 1) == first
    assert ledger.get_brief("CL-0003", "seed") == edited
    assert ledger.list_briefs("seed") == [first, edited]
    with pytest.raises(ValueError, match="Expected brief version 3"):
        add_brief(ledger, brief_version=2)
    assert len(ledger.list_briefs("seed")) == 2
    assert ledger.list_briefs("seed", "CL-0001") == []
    assert ledger.get_brief("CL-0001", "seed") is None
    with pytest.raises(sqlite3.IntegrityError):
        add_brief(ledger, "missing")


def test_concurrent_brief_versions_are_unique_and_contiguous(tmp_path):
    ledger = ReviewLedger(tmp_path / "ledger.sqlite3")
    add_run(ledger)
    with ThreadPoolExecutor(max_workers=6) as pool:
        versions = list(pool.map(lambda _: add_brief(ledger).brief_version, range(12)))
    assert sorted(versions) == list(range(1, 13))


def test_scoped_history_retained_when_returning_to_seed(tmp_path):
    ledger = ReviewLedger(tmp_path / "ledger.sqlite3")
    add_run(ledger)
    add_run(ledger, "update", is_seed=False)
    seed_brief = add_brief(ledger)
    update_brief = add_brief(ledger, "update")
    assert ledger.seed_run().run_id == "seed"
    assert ledger.list_briefs("seed") == [seed_brief]
    assert ledger.list_briefs("update") == [update_brief]
    assert len(ledger.list_runs()) == 2


def test_existing_sqlite_migrates_without_changing_reviews(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE reviews (
                review_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, action TEXT NOT NULL,
                reviewed_text TEXT NOT NULL, rm TEXT NOT NULL, timestamp TEXT NOT NULL
            )
        """)
        connection.execute("""
            INSERT INTO reviews VALUES (
                'original', 'CL-0003', 'Approve', 'Old review', 'Priscilla Ong',
                '2026-08-26T00:00:00+00:00'
            )
        """)
    ledger = ReviewLedger(path)
    records = ledger.list()
    assert len(records) == 1
    assert records[0].review_id == "original"
    assert records[0].text == "Old review"
    assert ledger.list("seed") == []
    assert ReviewLedger(path).list() == records
    assert not hasattr(ledger, "import_legacy_json")


def test_legacy_append_interface_remains_available():
    ledger = ReviewLedger(":memory:")
    request = ReviewRequest(client_id="CL-0003", action="Approve", text="Reviewed")
    record = ledger.append(request, rm="Priscilla Ong")
    assert ledger.list() == [record]
    assert ledger.list(client_id="CL-0001") == []
    ledger.close()
