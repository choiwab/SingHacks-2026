"""Qualitative source updates must reach generation without fabricating numeric Facts."""

import shutil

from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import DEFAULT_SOURCE_DIR
from app.pipeline.runtime import PipelineRuntime
from app.store import ReviewLedger


def test_note_only_update_regenerates_client_brief_and_reuses_unrelated_clients(tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    shutil.copy(DEFAULT_SOURCE_DIR / "fixtures/update/rm_notes.json", overlay)
    generated = []

    def wealth(state):
        generated.append(state["client_id"])
        notes = state["client_context"]["rm_notes"]
        return {
            "draft_brief": {
                "sections": {
                    "summary": {
                        "text": "\n".join(note["note"] for note in notes),
                        "citations": [note["evidence_id"] for note in notes],
                    }
                }
            }
        }

    service = PipelineRuntime(
        ArtifactStore(tmp_path / "curated"),
        ReviewLedger(tmp_path / "ledger.sqlite"),
        overlay_dir=overlay,
        agents=AgentHooks(
            context=lambda state: {},
            wealth=wealth,
            verifier=lambda state: {"verification_report": {"passed": True}},
        ),
    )
    seed = service.seed()
    updated = service.update()
    report = service.store.load_change_report("CL-0003")
    assert report.processing_mode == "incremental_update"
    assert report.changed_context_sections == ["rm_notes"]
    assert report.changed_fact_ids == []
    assert report.affected_signal_ids == []
    assert service.store.load_fact_bundle("CL-0003", run_id=seed.run_id).facts == (
        service.store.load_fact_bundle("CL-0003", run_id=updated.run_id).facts
    )
    before = service.ledger.get_brief("CL-0003", seed.run_id)
    after = service.ledger.get_brief("CL-0003", updated.run_id)
    assert before and after
    assert before.body["meeting_brief"] != after.body["meeting_brief"]
    assert generated[20:] == ["CL-0003"]
    for client in set(updated.client_ids) - {"CL-0003"}:
        assert service.store.load_change_report(client).processing_mode == "no_material_change"
        old = service.ledger.get_brief(client, seed.run_id)
        new = service.ledger.get_brief(client, updated.run_id)
        assert old and new and old.body == new.body


def test_transaction_only_update_replaces_brief_from_current_evidence(tmp_path):
    import csv

    overlay = tmp_path / "overlay"
    overlay.mkdir()
    with (DEFAULT_SOURCE_DIR / "transactions.csv").open() as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        row = next(row for row in reader if row["client_id"] == "CL-0003")
    row.update(
        transaction_id="TXN-NEW",
        trade_date="2026-08-25",
        settlement_date="2026-08-25",
        amount="1000",
        narrative="Transfer received for the upcoming family discussion.",
    )
    with (overlay / "transactions.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    generated = []

    def wealth(state):
        generated.append(state["client_id"])
        transactions = [
            entry
            for entry in state["evidence_map"].values()
            if entry["kind"] == "transactions"
            and entry["record"]["client_id"] == state["client_id"]
        ]
        return {
            "draft_brief": {
                "sections": {
                    "summary": {
                        "text": "\n".join(entry["record"]["narrative"] for entry in transactions)
                        or "No transaction history",
                        "citations": [entry["id"] for entry in transactions],
                    }
                }
            }
        }

    service = PipelineRuntime(
        ArtifactStore(tmp_path / "curated"),
        ReviewLedger(tmp_path / "ledger.sqlite"),
        overlay_dir=overlay,
        agents=AgentHooks(
            context=lambda state: {},
            wealth=wealth,
            verifier=lambda state: {"verification_report": {"passed": True}},
        ),
    )
    seed = service.seed()
    updated = service.update()
    report = service.store.load_change_report("CL-0003")
    assert report.processing_mode == "incremental_update"
    assert report.changed_context_sections == ["transactions"]
    assert report.changed_fact_ids == report.affected_signal_ids == []
    assert service.store.load_fact_bundle("CL-0003", run_id=seed.run_id).facts == (
        service.store.load_fact_bundle("CL-0003", run_id=updated.run_id).facts
    )
    previous = service.ledger.get_brief("CL-0003", seed.run_id)
    current = service.ledger.get_brief("CL-0003", updated.run_id)
    assert previous and current
    assert (
        "transactions:TXN-NEW"
        not in previous.body["meeting_brief"]["sections"]["summary"]["citations"]
    )
    assert (
        "transactions:TXN-NEW" in current.body["meeting_brief"]["sections"]["summary"]["citations"]
    )
    assert row["narrative"] in current.body["meeting_brief"]["sections"]["summary"]["text"]
    assert generated[20:] == ["CL-0003"]
    for client in set(updated.client_ids) - {"CL-0003"}:
        assert service.store.load_change_report(client).processing_mode == "no_material_change"
        old = service.ledger.get_brief(client, seed.run_id)
        new = service.ledger.get_brief(client, updated.run_id)
        assert old and new and old.body == new.body
