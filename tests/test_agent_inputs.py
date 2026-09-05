"""Read-only, real dataset checks for the agent's published inputs."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.pipeline.agent_inputs import load_curated_bundle, load_dataset_notes
from app.pipeline.errors import SourceValidationError

DATA = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 8, 26)


def test_real_bundle_is_cited_scoped_and_content_versioned():
    bundle = load_curated_bundle(DATA, "CL-0003", AS_OF)
    same = load_curated_bundle(DATA, "CL-0003", AS_OF, revision="different-label")
    assert bundle == same
    assert len(bundle.signals) == 3
    assert len({signal.score for signal in bundle.signals}) > 1
    assert {fact.kind for fact in bundle.facts} >= {"profile", "change", "mandate_gap", "deadline"}
    for signal in bundle.signals:
        assert signal.score == next(iter(signal.components.values()))
    for fact in bundle.facts:
        assert fact.id.startswith("CL-0003:fact:")
        assert set(fact.source_rows + fact.event_ids) <= bundle.evidence.keys()
    change_signal = next(signal for signal in bundle.signals if "portfolio-change" in signal.id)
    assert "not investment returns" in change_signal.uncertainty
    assert "not proof of causation" in change_signal.uncertainty
    assert len(change_signal.fact_ids) == 3


@pytest.mark.parametrize("as_of", [date(2026, 2, 27), date(2026, 6, 30)])
def test_historical_bundle_never_cites_future_snapshot_or_event(as_of):
    bundle = load_curated_bundle(DATA, "CL-0002", as_of)
    for evidence in bundle.evidence.values():
        for field in ("snapshot_date", "event_date"):
            if field in evidence.record:
                assert date.fromisoformat(evidence.record[field]) <= as_of
    changes = [fact for fact in bundle.facts if fact.kind == "change"]
    for fact in changes:
        assert any(as_of.isoformat() in identifier for identifier in fact.source_rows)


def test_notes_are_exact_source_records_not_invented_connected_messages():
    notes = json.loads((DATA / "rm_notes.json").read_text())
    by_id = {f"notes:{note['note_id']}": note for note in notes}
    context = load_dataset_notes(DATA, "CL-0003", datetime(2026, 8, 26, tzinfo=UTC))
    assert [record.id for record in context.records] == ["notes:N-005", "notes:N-006"]
    assert context.sources == {
        "gmail": "Not connected",
        "teams": "Not connected",
        "notes": "Cached",
        "calendar": "Not connected",
    }
    for record in context.records:
        original = by_id[record.id]
        assert record.text == original["note"]
        assert record.provenance == "dataset"
        assert record.based_on == [f"data/rm_notes.json:{original['note_id']}"]
        assert record.client_id == "CL-0003"
    earlier = load_dataset_notes(DATA, "CL-0003", datetime(2026, 3, 1, tzinfo=UTC))
    assert [record.id for record in earlier.records] == ["notes:N-005"]
    assert earlier.records[0].version == context.records[0].version
    empty = load_dataset_notes(DATA, "CL-0003", datetime(2025, 1, 1, tzinfo=UTC))
    assert empty.records == []
    assert empty.sources["notes"] == "Cached"


def test_unknown_clients_and_unavailable_snapshot_fail_explicitly():
    with pytest.raises(ValueError, match="Unknown client"):
        load_curated_bundle(DATA, "CL-9999", AS_OF)
    with pytest.raises(ValueError, match="Unknown client"):
        load_dataset_notes(DATA, "CL-9999", datetime(2026, 8, 26, tzinfo=UTC))
    with pytest.raises(SourceValidationError):
        load_curated_bundle(DATA, "CL-0003", date(2026, 8, 27))
    with pytest.raises(ValueError, match="aware"):
        load_dataset_notes(DATA, "CL-0003", datetime(2026, 8, 26))
