"""Real M2 generation over all 20 clients, with the missing M4 gate disclosed."""

import socket

import pytest

from app.agents import generation
from app.mcp.connectors import replay_records
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
        store, ledger, agents=member2_hooks(store, load_communications=communications)
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
