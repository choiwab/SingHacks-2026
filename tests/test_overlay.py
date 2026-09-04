from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline.overlay import apply_overlay
from app.pipeline.stages.ingest import IngestedSources, ingest_sources
from app.pipeline.stages.validate import validate_sources

DATA = Path(__file__).parents[1] / "data"
AS_OF = date(2026, 8, 26)


def test_fixture_roundtrip_keeps_base_unchanged_and_retains_original_provenance():
    base = ingest_sources(DATA, as_of=AS_OF)
    original = base.tables["planned_cash_needs"].copy(deep=True)
    result = apply_overlay(base.tables, base.notes, DATA / "fixtures/update")
    updated = IngestedSources(result.tables, result.notes, AS_OF)
    assert not validate_sources(updated).has_errors
    pd.testing.assert_frame_equal(base.tables["planned_cash_needs"], original)
    need = result.tables["planned_cash_needs"].set_index("need_id").loc["CN-004"]
    assert need["amount"] == 3400000
    assert need["due_from"] == "2026-09-01"
    assert len(result.notes) == 29
    assert result.overridden_keys == {
        "planned_cash_needs.csv": ["CN-004"],
        "rm_notes.json": ["N-029"],
    }
    assert (
        result.provenance["planned_cash_needs:CN-004"]["source_file"]
        == "fixtures/update/planned_cash_needs.csv"
    )
    assert result.provenance["planned_cash_needs:CN-004"]["row_index"] == 2
    assert result.provenance["planned_cash_needs:CN-004"]["original_row_index"] == 5
    assert result.provenance["rm_notes:N-029"]["row_index"] == 1
    assert result.provenance["planned_cash_needs:CN-005"]["row_index"] == 6
    assert result.tables["planned_cash_needs"]["amount"].dtype.kind == "f"


@pytest.mark.parametrize("field,value", [("amount", "broken"), ("due_from", "tomorrow")])
def test_overlay_bad_numeric_and_date_values_fail_before_merge(tmp_path, field, value):
    base = ingest_sources(DATA, as_of=AS_OF)
    row = pd.read_csv(DATA / "planned_cash_needs.csv", dtype=str).iloc[[3]].copy()
    row[field] = value
    row.to_csv(tmp_path / "planned_cash_needs.csv", index=False)
    with pytest.raises(ValueError, match="invalid_"):
        apply_overlay(base.tables, base.notes, tmp_path)


def test_duplicate_overlay_key_is_rejected(tmp_path):
    base = ingest_sources(DATA, as_of=AS_OF)
    row = pd.read_csv(DATA / "clients.csv", dtype=str).iloc[[0]]
    pd.concat([row, row]).to_csv(tmp_path / "clients.csv", index=False)
    with pytest.raises(ValueError, match="duplicate"):
        apply_overlay(base.tables, base.notes, tmp_path)


def test_overlay_addition_preserves_existing_note_and_row_positions(tmp_path):
    import json

    base = ingest_sources(DATA, as_of=AS_OF)
    note = dict(base.notes[0], note_id="N-030", note_date="2026-08-25")
    (tmp_path / "rm_notes.json").write_text(json.dumps([note]))
    result = apply_overlay(base.tables, base.notes, tmp_path)
    assert result.notes[:-1] == base.notes
    assert result.notes[-1] == note
    assert result.provenance["rm_notes:N-001"]["row_index"] == 1
    assert result.provenance["rm_notes:N-030"]["source_path"] == str(
        (tmp_path / "rm_notes.json").resolve()
    )
    assert result.provenance["rm_notes:N-030"]["original_row_index"] is None


def test_overlay_rejects_partial_rows(tmp_path):
    base = ingest_sources(DATA, as_of=AS_OF)
    (tmp_path / "planned_cash_needs.csv").write_text("need_id,amount\nCN-004,3400000\n")
    with pytest.raises(ValueError, match="complete source columns"):
        apply_overlay(base.tables, base.notes, tmp_path)
