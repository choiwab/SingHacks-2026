"""Durable Connected Records retain versions without crossing clients or As-of Dates."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.contracts import ReviewAction, fingerprint
from app.mcp.records import CommunicationRecord
from app.mcp.retrieval import MemoryIndex
from app.mcp.store import MemoryStore

CUTOFF = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)


def note(**changes):
    return CommunicationRecord.model_validate(
        {
            "id": "notes:meeting-1",
            "client_id": "CL-0003",
            "source": "notes",
            "version": "1",
            "occurred_at": CUTOFF - timedelta(days=1),
            "retrieved_at": CUTOFF,
            "participants": ["Relationship Manager"],
            "text": "Client prefers a written explanation before the meeting.",
            "topics": ["personality_and_style"],
            "provenance": "synthetic_fixture",
            **changes,
        }
    )


def test_restart_retains_source_versions_and_reconstructs_precise_retrieval(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    original = note()
    store.put(original)
    store.put(note(retrieved_at=CUTOFF + timedelta(days=1)))
    replacement = note(version="2", text="Client now prefers a short phone call.")
    store.put(replacement)
    store.put(original)  # replaying an old version cannot revert the current one
    restarted = MemoryStore(path)
    assert restarted.history("CL-0003", original.id) == [original, replacement]
    context = restarted.context("CL-0003", CUTOFF)
    assert context.records == [replacement]
    index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    index.update(context.records)
    hit = index.search("phone call", topic="personality_and_style")[0]
    assert hit["text"] == replacement.text[hit["start"] : hit["end"]]
    assert context.sources == {
        "gmail": "Not connected",
        "teams": "Not connected",
        "notes": "Cached",
        "calendar": "Not connected",
    }
    assert context.retrieval_log[0]["mode"] == "persistent_memory"


def test_store_rejects_version_rewrites_and_cross_client_record_ownership(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.put(note())
    with pytest.raises(ValueError, match="Conflicting content"):
        store.put(note(text="Silent rewrite"))
    with pytest.raises(ValueError, match="different client"):
        store.put(note(client_id="CL-0012", version="2"))
    store.put(note(id="notes:other-client", client_id="CL-0012"))
    assert [r.id for r in store.context("CL-0012", CUTOFF).records] == ["notes:other-client"]
    assert store.history("CL-0012", "notes:meeting-1") == []
    with pytest.raises(ValueError, match="client ID"):
        store.context("", CUTOFF)
    with pytest.raises(ValueError, match="aware"):
        store.context("CL-0003", CUTOFF.replace(tzinfo=None))


def test_latest_eligible_version_and_cached_live_provenance(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    record = note(provenance="recorded_live", availability="Live")
    store.put(record)
    store.put(note(version="2", occurred_at=CUTOFF + timedelta(days=1), text="Future update"))
    current = store.context("CL-0003", CUTOFF).records
    assert len(current) == 1
    assert current[0].version == "1"
    assert current[0].availability == "Cached"
    assert current[0].provenance == "recorded_live"
    assert store.context("CL-0003", CUTOFF + timedelta(days=2)).records[0].version == "2"
    assert store.context("CL-0003", CUTOFF - timedelta(days=2)).records == []


def test_review_sink_is_validated_durable_and_idempotent(tmp_path):
    path = tmp_path / "memory.sqlite3"
    review = ReviewAction(client_id="CL-0003", pack_version="verified-pack", action="Approve")
    payload = review.model_dump(mode="json")
    event = {"event_id": fingerprint(payload), **payload}
    MemoryStore(path).record_review(event)
    MemoryStore(path).record_review(event)
    with pytest.raises(ValueError, match="event ID"):
        MemoryStore(path).record_review({**event, "action": "Reject"})
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM memory_reviews").fetchone()[0] == 1
    finally:
        connection.close()
