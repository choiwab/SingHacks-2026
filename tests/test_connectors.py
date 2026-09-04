"""Fixture replay must disclose origin and availability without pretending to call MCP."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.mcp.connectors import replay_records
from app.mcp.records import CommunicationRecord
from scripts.member_2_demo import FIXTURES

CUTOFF = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)


def test_fixture_provenance_sources_logs_and_client_scope():
    context = replay_records(
        FIXTURES / "communications.initial.json", client_id="CL-0003", as_of=CUTOFF
    )
    assert set(context.sources.values()) == {"Cached"}
    assert all(r.provenance == "synthetic_fixture" for r in context.records)
    assert all(log["mode"] == "fixture_replay" for log in context.retrieval_log)
    wrong = replay_records(
        FIXTURES / "communications.initial.json", client_id="CL-0014", as_of=CUTOFF
    )
    assert wrong.records == []
    assert set(wrong.sources.values()) == {"Not connected"}


def test_missing_source_is_not_connected(tmp_path):
    context = replay_records(tmp_path / "missing.json", client_id="CL-0003", as_of=CUTOFF)
    assert not context.records
    assert set(context.sources.values()) == {"Not connected"}


def test_synthetic_record_cannot_claim_live_and_future_is_excluded():
    records = json.loads((FIXTURES / "communications.initial.json").read_text())
    with pytest.raises(ValidationError, match="cannot claim"):
        CommunicationRecord.model_validate({**records[0], "availability": "Live"})
    early = replay_records(
        FIXTURES / "communications.updated.json",
        client_id="CL-0003",
        as_of=datetime(2026, 8, 25, 23, 59, tzinfo=UTC),
    )
    assert all(r.id != "gmail:changed-priorities" for r in early.records)


def test_conflicting_duplicate_ids_fail_instead_of_overwriting(tmp_path):
    records = json.loads((FIXTURES / "communications.initial.json").read_text())
    records.append({**records[0], "text": "Conflicting copy"})
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        replay_records(path, client_id="CL-0003", as_of=CUTOFF)
