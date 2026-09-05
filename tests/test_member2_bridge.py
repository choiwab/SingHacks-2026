"""Real M2 generation over all 20 clients, with the missing M4 gate disclosed."""

import socket

import pytest

from app.agents import generation
from app.mcp.connectors import replay_records
from app.pipeline.features import legacy_analytics
from app.pipeline.loaders import ArtifactStore
from app.pipeline.member2_bridge import member2_hooks
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger
from scripts.member_2_demo import FIXTURES


def test_real_offline_seed_update_persists_generation_without_approving_unverified(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline generation attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(generation, "request_narration", forbidden)
    store = ArtifactStore(tmp_path / "curated")

    def communications(client, as_of, revision):
        manifest = store.load_manifest(revision)
        name = "updated" if manifest.overlay_hashes else "initial"
        return replay_records(
            FIXTURES / f"communications.{name}.json", client_id=client, as_of=as_of
        )

    ledger = ReviewLedger(tmp_path / "ledger.sqlite")
    runtime = PipelineRuntime(
        store,
        ledger,
        analytics=legacy_analytics,
        agents=member2_hooks(store, load_communications=communications),
    )
    seed = runtime.seed()
    assert len(seed.client_ids) == 20
    for client in seed.client_ids:
        brief = ledger.get_brief(client, seed.run_id)
        assert brief is not None
        assert brief.body["pack"]["client_id"] == client
        assert brief.body["pack"]["generation_mode"] == "deterministic"
        assert brief.body["pack_version"]
        assert brief.body["insights"] == []  # No invented financial Signals.
        assert brief.body["memory_index"]["client_id"] == client
        assert [item["node"] for item in brief.body["trace"]] == ["context", "wealth", "briefing"]
        assert brief.verification_report["passed"] is False
        assert (
            "Phase A Signal definitions are not connected; legacy Facts only."
            in brief.body["context_issues"]
        )
        if client != "CL-0003":
            assert brief.body["connected_context"] == []
            assert set(brief.body["connected_sources"].values()) == {"Not connected"}
    before = ledger.get_brief("CL-0003", seed.run_id)
    assert before is not None and before.body["connected_context"]
    with pytest.raises(ValueError, match="not passed verification"):
        runtime.review(
            ReviewRequest(
                client_id="CL-0003", run_id=seed.run_id, brief_version=1, action="Approve"
            )
        )
    update = runtime.update()
    assert len(ledger.list_briefs(update.run_id)) == 20
    after = ledger.get_brief("CL-0003", update.run_id)
    assert after is not None
    assert after.body["pack_version"] != before.body["pack_version"]
    assert (
        after.body["memory_index"]["record_versions"]
        != before.body["memory_index"]["record_versions"]
    )
    assert len(after.body["connected_context"]) > len(before.body["connected_context"])
    # Rehydrate from committed persistence, without requiring live model/checkpoint state.
    restored = PipelineRuntime(store, ReviewLedger(tmp_path / "ledger.sqlite"))
    restored.prepare_current()
    reloaded = restored.ledger.get_brief("CL-0003", update.run_id)
    assert reloaded is not None and reloaded.body == after.body

    # Editing after a restart requires the pack adapter, never the legacy section editor.
    request = ReviewRequest(
        client_id="CL-0003",
        run_id=update.run_id,
        brief_version=1,
        action="Edit",
        section="opening",
        text="Could we discuss your priorities?",
    )
    with pytest.raises(ValueError, match="configured agent adapter"):
        restored.review(request)
    seen = []

    def failing_gate(state):
        from app.agents.contracts import MeetingPack

        pack = MeetingPack.model_validate(state["pack"])
        assert state["pack_version"] == pack.version
        assert state["meeting_brief"]["sections"] == pack.brief.model_dump(mode="json")
        assert state["memory_index"] == after.body["memory_index"]
        assert state["connected_context"] == after.body["connected_context"]
        seen.append(pack)
        return {
            "verification_report": {
                "passed": False,
                "errors": ["Explicit failing test gate"],
                "pack_version": pack.version,
            }
        }

    from dataclasses import replace

    assert runtime.agents is not None
    runtime.agents = replace(runtime.agents, verifier=failing_gate)
    with pytest.raises(KeyError, match="Only the opening"):
        runtime.review(request.model_copy(update={"section": "summary"}))
    result = runtime.review(request)
    edited = ledger.get_brief("CL-0003", update.run_id)
    assert edited is not None and edited.brief_version == 2
    assert result["verification_report"]["passed"] is False
    assert len(seen) == 1
    assert edited.body["pack_version"] != after.body["pack_version"]
    assert edited.body["pack"]["brief"]["opening"]["text"] == request.text
    assert edited.body["pack"]["brief"]["opening"]["authorship"] == "rm"
    original = ledger.get_brief("CL-0003", update.run_id, 1)
    assert original is not None and original.body == after.body
    with pytest.raises(ValueError, match="not passed verification"):
        runtime.review(request.model_copy(update={"action": "Approve", "brief_version": 2}))
    with pytest.raises(ValueError, match="no longer current"):
        runtime.review(request)


def test_pack_editor_changes_only_named_talking_point_and_preserves_source_artifacts():
    from copy import deepcopy

    from app.agents.contracts import MeetingPack
    from app.pipeline.member2_bridge import edit_pack, project_pack

    pack = MeetingPack.model_validate_json((FIXTURES / "golden.initial.json").read_text())
    body = {**project_pack(pack), "memory_index": {"chunks": {"fixture": "unchanged"}}}
    original = deepcopy(body)
    target = pack.brief.talking_points[0].id
    edited = edit_pack(body, target, "Could we review this finding together?")
    assert body == original
    updated_pack = MeetingPack.model_validate(edited["pack"])
    assert edited["pack_version"] == updated_pack.version != pack.version
    for before, after in zip(pack.claims(), updated_pack.claims(), strict=True):
        if before.id == target:
            assert after.text == "Could we review this finding together?"
            assert after.authorship == "rm"
            assert after.citations == before.citations
        else:
            assert after == before
    assert edited["memory_index"] == original["memory_index"]
    for readonly in (pack.brief.summary[0].id, pack.brief.questions[0].id):
        with pytest.raises(KeyError, match="Only the opening"):
            edit_pack(body, readonly, "Invalid edit")
    with pytest.raises(ValueError, match="does not match"):
        edit_pack({**body, "pack_version": "stale"}, target, "Invalid edit")
