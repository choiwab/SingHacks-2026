"""Retrieval behavior: scope, precise citations, edits, deletions and deterministic ordering."""

from datetime import UTC, datetime

from app.mcp.retrieval import MemoryIndex
from scripts.member_2_demo import load_communications

CUTOFF = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)


def test_topic_retrieval_is_stable_and_resolves_exact_source_spans():
    records = load_communications("CL-0003", CUTOFF, "initial").records
    index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    index.update(records)
    hits = index.search("plain language written", topic="personality_and_style")
    assert hits[0]["record_id"] == "teams:communication"
    by_id = {r.id: r for r in records}
    assert all(h["text"] == by_id[h["record_id"]].text[h["start"] : h["end"]] for h in hits)
    reversed_index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    reversed_index.update(list(reversed(records)))
    assert reversed_index.search("plain language written", topic="personality_and_style") == hits
    assert reversed_index.version == index.version
    assert index.search("something", topic="no_such_topic") == []


def test_index_filters_client_and_future_and_handles_edits_removal_and_duplicates():
    records = load_communications("CL-0003", CUTOFF, "initial").records
    index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    other = records[0].model_copy(update={"id": "notes:other", "client_id": "CL-0014"})
    future = records[0].model_copy(
        update={"id": "notes:future", "occurred_at": datetime(2027, 1, 1, tzinfo=UTC)}
    )
    index.update([*records, records[0], other, future])
    assert "notes:other" not in index.record_versions
    assert "notes:future" not in index.record_versions
    assert index.update(records) == []
    before = dict(index.chunks)
    revised = records[0].model_copy(
        update={"text": "Corrected relationship history", "version": "2"}
    )
    removed = records[1].id
    changed = index.update([revised, *records[2:]])
    assert changed == sorted([revised.id, removed])
    assert not any(c["record_id"] == removed for c in index.chunks.values())
    assert not any(c["text"] == records[0].text for c in index.chunks.values())
    untouched = [key for key, chunk in before.items() if chunk["record_id"] == records[2].id]
    assert all(index.chunks[key] is before[key] for key in untouched)


def test_retrieval_timestamp_alone_does_not_change_content_version():
    records = load_communications("CL-0003", CUTOFF, "initial").records
    index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    index.update(records)
    before = index.version
    replayed = [
        r.model_copy(update={"retrieved_at": datetime(2026, 9, 1, tzinfo=UTC)}) for r in records
    ]
    assert index.update(replayed) == []
    assert index.version == before


def test_latest_update_is_retrievable_with_its_original_preferences_retained():
    records = load_communications("CL-0003", CUTOFF, "updated").records
    index = MemoryIndex(client_id="CL-0003", as_of=CUTOFF)
    index.update(records)
    assert (
        index.search("recent", topic="recent_updates")[0]["record_id"] == "gmail:changed-priorities"
    )
    hits = index.search("portfolio", topic="stated_needs_and_goals", limit=10)
    assert {"notes:initial-intent", "gmail:changed-priorities"} <= {h["record_id"] for h in hits}
