"""Read-only application projection and health-state contracts."""

import json
from hashlib import sha256

import pytest
from test_loaders import CLIENT, SEED, UPDATE, publish_fixture, write

from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.schemas import ReviewRequest
from app.pipeline.view_model import build_view_model
from app.store import ReviewLedger


def setup_projection(tmp_path):
    root = tmp_path / "curated"
    run = publish_fixture(root)
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["client_ids"] = [CLIENT]
    source = tmp_path / "source"
    source.mkdir()
    (source / "clients.csv").write_text("original")
    manifest["source_hashes"] = {"clients.csv": sha256(b"original").hexdigest()}
    write(run / "manifest.json", manifest)
    ledger = ReviewLedger(tmp_path / "ledger.sqlite3")
    ledger.add_run(
        run_id=SEED,
        pipeline_version="1",
        as_of=manifest["as_of"],
        source_hashes=manifest["source_hashes"],
        is_seed=True,
    )
    return root, run, source, ledger


def store_brief(ledger, *, body=None, verification=None, run_id=SEED):
    return ledger.store_brief(
        client_id=CLIENT,
        run_id=run_id,
        body=body
        if body is not None
        else {
            "meeting_brief": {
                "sections": {"opening": {"text": "Discuss plans", "citations": ["rm_notes:N-005"]}}
            },
        },
        verification_report=verification if verification is not None else {"passed": True},
    )


def rewrite(path, **updates):
    value = json.loads(path.read_text())
    value.update(updates)
    write(path, value)


def test_projection_is_read_only_and_uses_current_persisted_version(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    first = store_brief(ledger)
    second = store_brief(
        ledger,
        body={
            "meeting_brief": {"sections": {"opening": {"text": "Updated"}}},
            "memory_card": {"summary": "Existing memory"},
        },
    )
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert model == build_view_model(ArtifactStore(root), ledger, source)
    assert model.data_health == "Current"  # Warning findings never alter health.
    assert model.clients[CLIENT].brief_status == "Ready"
    assert model.clients[CLIENT].brief_version == second.brief_version
    assert model.clients[CLIENT].meeting_brief == {
        "sections": {"opening": {"text": "Updated"}},
    }
    assert model.clients[CLIENT].memory_card == {"summary": "Existing memory"}
    assert model.calendar == []
    assert "selected" not in model.model_dump()
    assert before == {path: path.read_bytes() for path in root.rglob("*.json")}
    assert ledger.get_brief(CLIENT, SEED, 1) == first
    assert len(ledger.list_briefs(SEED)) == 2


@pytest.mark.parametrize(
    "brief",
    [
        None,
        {},
        {"sections": {}},
        {"sections": {"opening": {"text": ""}}},
        {"sections": {"opening": {"text": "Valid"}, "risks": []}},
    ],
)
def test_empty_brief_sections_are_not_prepared_even_with_passing_gate(tmp_path, brief):
    root, _run, source, ledger = setup_projection(tmp_path)
    store_brief(ledger, body={"meeting_brief": brief})
    assert build_view_model(ArtifactStore(root), ledger, source).clients[CLIENT].brief_status == (
        "Not prepared"
    )


def test_health_precedence_gate_context_errors_staleness_and_updating(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    store = ArtifactStore(root)
    assert build_view_model(store, ledger, source).data_health == "Current"
    assert build_view_model(store, ledger, source, updating=True).data_health == "Updating"
    (source / "clients.csv").write_text("changed")
    assert build_view_model(store, ledger, source, updating=True).data_health == "Stale"
    store_brief(ledger, verification={"passed": False, "errors": ["Unverified"]})
    model = build_view_model(store, ledger, source, updating=True)
    assert model.data_health == "Needs confirmation"
    assert model.clients[CLIENT].brief_status == "Needs review"
    store_brief(ledger, body={"context_issues": ["Calendar unavailable"]})
    assert build_view_model(store, ledger, source).data_health == "Needs confirmation"
    store_brief(ledger, body={})
    rewrite(run / "manifest.json", context_issues=["Signal definitions missing"])
    assert build_view_model(store, ledger, source).data_health == "Needs confirmation"
    rewrite(run / "manifest.json", context_issues=[])
    rewrite(
        run / "data_quality_report.json",
        findings=[
            {
                "code": "ERROR",
                "severity": "error",
                "message": "Broken",
                "client_id": CLIENT,
            }
        ],
    )
    assert build_view_model(store, ledger, source).data_health == "Needs confirmation"


def test_insight_change_labels_and_calendar_use_connected_records_only(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    rewrite(
        run / "change_report" / f"{CLIENT}.json",
        signal_changes=[
            {"signal_id": "s-new", "change": "added"},
            {"signal_id": "s-change", "change": "changed"},
        ],
    )
    meeting = {"type": "calendar", "id": "meeting-1", "date": "2026-09-06", "title": "Client call"}
    other = {"type": "email", "id": "mail-1", "text": "Existing context"}
    store_brief(
        ledger,
        body={
            "insights": [
                {"signal_id": identifier, "text": "Existing insight"}
                for identifier in ["s-new", "s-change", "s-old", "s-fourth"]
            ],
            "connected_context": [meeting, other],
        },
    )
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert [item["change_status"] for item in model.clients[CLIENT].insights] == [
        "New",
        "Changed",
        "Unchanged",
    ]
    assert model.calendar == [meeting]
    assert model.clients[CLIENT].memory_tab == [meeting, other]


def test_fact_values_and_nested_evidence_are_preserved_without_extra_entries(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    evidence_id = "rm_notes:N-005"
    fact = {
        "id": "f1",
        "client_id": CLIENT,
        "kind": "cash_need.amount",
        "value": 3400000,
        "unit": "currency",
        "currency": "EUR",
        "formula_id": "cash_need.amount",
        "evidence_ids": [evidence_id],
        "as_of": "2026-08-26",
        "confidence": 1,
    }
    rewrite(run / "fact_bundle" / f"{CLIENT}.json", facts=[fact])
    store_brief(
        ledger,
        body={
            "meeting_brief": {
                "sections": {"opening": {"text": "Discuss cash", "citations": ["f1"]}}
            },
            "memory_card": {"nested": {"evidence_ids": [evidence_id]}},
        },
    )
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert model.clients[CLIENT].data_tab.cash_need[0].value == 3400000
    assert list(model.evidence) == [evidence_id]
    assert model.evidence[evidence_id].record == {"note": SEED}
    store_brief(ledger, body={"memory_card": {"citations": ["missing"]}})
    with pytest.raises(ArtifactNotFound, match="missing"):
        build_view_model(ArtifactStore(root), ledger, source)


def test_missing_brief_and_overlay_staleness(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    rewrite(run / "manifest.json", overlay_hashes={"rm_notes.json": sha256(b"[]").hexdigest()})
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert model.clients[CLIENT].brief_status == "Not prepared"
    assert model.data_health == "Stale"
    write(source / "fixtures/update/rm_notes.json", [])
    assert build_view_model(ArtifactStore(root), ledger, source).data_health == "Current"


def test_reviews_are_filtered_to_active_run(tmp_path):
    root, _run, source, ledger = setup_projection(tmp_path)
    store_brief(ledger)
    ledger.add_run(run_id=UPDATE, pipeline_version="1", as_of="2026-08-26", source_hashes={})
    store_brief(ledger, run_id=UPDATE)
    for run_id in [SEED, UPDATE]:
        ledger.append(
            ReviewRequest(
                client_id=CLIENT,
                run_id=run_id,
                brief_version=1,
                action="Approve",
            ),
            rm="RM",
        )
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert len(model.reviews) == 1
    assert model.reviews[0].run_id == SEED


def test_rm_notes_are_retained_and_referenced_evidence_is_included(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    note = {
        "note_id": "N-005",
        "client_id": CLIENT,
        "note_date": "2026-08-24",
        "rm_id": "RM1",
        "rm_name": "RM",
        "channel": "call",
        "note": "Existing note",
        "evidence_id": "rm_notes:N-005",
    }
    rewrite(run / "curated_client_bundle" / f"{CLIENT}.json", rm_notes=[note])
    model = build_view_model(ArtifactStore(root), ledger, source)
    assert model.clients[CLIENT].memory_tab == [note]
    assert list(model.evidence) == [note["evidence_id"]]


def test_overlay_added_modified_and_removed_files_mark_applied_run_stale(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    overlay = source / "fixtures/update"
    write(overlay / "rm_notes.json", [])
    rewrite(run / "manifest.json", overlay_hashes={"rm_notes.json": sha256(b"[]").hexdigest()})
    store = ArtifactStore(root)
    assert build_view_model(store, ledger, source).data_health == "Current"
    write(overlay / "planned_cash_needs.csv", {})
    assert build_view_model(store, ledger, source).data_health == "Stale"
    (overlay / "planned_cash_needs.csv").unlink()
    write(overlay / "rm_notes.json", [{}])
    assert build_view_model(store, ledger, source).data_health == "Stale"
    (overlay / "rm_notes.json").unlink()
    assert build_view_model(store, ledger, source).data_health == "Stale"


def test_failed_verification_suppresses_generated_claims_but_retains_editable_draft(tmp_path):
    root, _run, source, ledger = setup_projection(tmp_path)
    draft = {
        "meeting_brief": {"sections": {"opening": {"text": "UNVERIFIED_BRIEF_CLAIM"}}},
        "insights": [{"text": "UNVERIFIED_INSIGHT_CLAIM"}],
        "memory_card": {"summary": "UNVERIFIED_MEMORY_CLAIM"},
    }
    record = store_brief(
        ledger, body=draft, verification={"passed": False, "errors": ["Failed gate"]}
    )
    model = build_view_model(ArtifactStore(root), ledger, source)
    client = model.clients[CLIENT]
    assert client.meeting_brief is None
    assert client.insights == []
    assert client.memory_card is None
    assert client.brief_version == record.brief_version
    assert client.brief_status == "Needs review"
    assert client.verification == {"passed": False, "errors": ["Failed gate"]}
    assert "UNVERIFIED_" not in model.model_dump_json()
    stored = ledger.get_brief(CLIENT, SEED)
    assert stored is not None
    assert stored.body == draft


def test_header_only_exposes_qualitative_profile_fields(tmp_path):
    root, _run, source, ledger = setup_projection(tmp_path)
    model = build_view_model(ArtifactStore(root), ledger, source)
    header = model.clients[CLIENT].header.model_dump()
    assert header["client_id"] == CLIENT
    assert header["client_name"] == "Example"
    assert header["risk_profile"] == "Conservative"
    assert not {"age", "total_aum_usd", "risk_tolerance_score", "investment_horizon_years"} & set(
        header
    )
    assert all(isinstance(value, str) for value in header.values())
