"""Existing graph integration with pinned Phase A Facts and original RM notes."""

import json
import shutil
import socket
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from app.agents.contracts import CuratedClientBundle, MeetingPack
from app.pipeline.agent_inputs import load_dataset_notes
from app.pipeline.runner import run_pipeline
from scripts.dry_run_agents import dry_run_agents
from scripts.run_client_flow import build_data_flow

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 8, 26)


def test_source_helper_separates_generation_modes_and_honors_policy_override(monkeypatch):
    import scripts.run_client_flow as runner

    monkeypatch.setattr(runner, "build_agent_flow", lambda **kwargs: kwargs)
    offline_policy = runner.build_data_flow(ROOT / "data")["generation_policy"]
    live_policy = runner.build_data_flow(ROOT / "data", live_generation=True)["generation_policy"]
    assert offline_policy.endswith(":deterministic")
    assert live_policy.endswith(":openai")
    assert offline_policy != live_policy
    custom = runner.build_data_flow(ROOT / "data", generation_policy="custom-policy")
    assert custom["generation_policy"] == "custom-policy"


@pytest.fixture(scope="module")
def published_sources(tmp_path_factory):
    source_dir = tmp_path_factory.mktemp("agent-wiring") / "data"
    shutil.copytree(ROOT / "data", source_dir, ignore=shutil.ignore_patterns("generated"))
    manifest = run_pipeline(
        source_dir=source_dir,
        as_of=AS_OF,
        curated_dir=source_dir / "generated/curated",
        activate=False,
    )
    return source_dir, manifest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Agent wiring checks must not access the network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def invoke(graph, manifest, client_id):
    return graph.invoke(
        {
            "run_id": manifest.run_id,
            "client_id": client_id,
            "as_of": AS_OF.isoformat(),
            "revision": manifest.run_id,
            "trace": [],
        },
        config={"configurable": {"thread_id": f"wiring:{client_id}"}},
    )


def test_offline_batch_reaches_review_for_every_client_without_approval(published_sources):
    source_dir, manifest = published_sources
    summary = dry_run_agents(source_dir, AS_OF, run_id=manifest.run_id)
    assert summary["client_count"] == 20
    assert summary["all_awaiting_review"]
    assert summary["pipeline_run_id"] == manifest.run_id
    assert all(client["verification"]["passed"] for client in summary["clients"])
    assert all(client["review_required"] for client in summary["clients"])
    assert all(client["status"] == "awaiting_review" for client in summary["clients"])


def test_margarethe_tax_request_survives_unchanged_input_reuse(published_sources):
    source_dir, manifest = published_sources
    graph = build_data_flow(source_dir)
    first = invoke(graph, manifest, "CL-0003")
    pack = MeetingPack.model_validate(first["pack"])
    assert any(
        request.code == "PHASE_A_TRANSFER_TAX_BASIS_UNVERIFIED"
        and "estate executor" in request.request.text
        for request in pack.information_requests
    )
    assert any("funding_gap" in insight.signal_id for insight in pack.insights)
    assert any("mandate_" in insight.signal_id for insight in pack.insights)
    unchanged = invoke(graph, manifest, "CL-0003")
    assert unchanged["processing_mode"] == "no_material_change"
    assert unchanged["pack_version"] == first["pack_version"]
    assert unchanged["status"] == "awaiting_review"
    assert unchanged.get("last_approved") is None


@pytest.mark.parametrize(
    "client_id,code,limitation",
    [
        ("CL-0003", "lookthrough_unavailable", "unscreenable, not zero"),
        ("CL-0014", "accumulator_forward_exposure", "forward accumulation"),
        ("CL-0002", "PHASE_A_MATERIAL_STALE_VALUATION", "stale valuation"),
    ],
)
def test_material_missing_information_is_disclosed(published_sources, client_id, code, limitation):
    source_dir, manifest = published_sources
    state = invoke(build_data_flow(source_dir), manifest, client_id)
    pack = MeetingPack.model_validate(state["pack"])
    assert state["verification"]["passed"]
    assert any(request.code == code for request in pack.information_requests)
    assert any(limitation in claim.text for claim in pack.brief.uncertainty)


def test_pinned_notes_and_pack_ignore_later_raw_note_edits(published_sources, tmp_path):
    source_dir, manifest = published_sources
    copied = tmp_path / "data"
    shutil.copytree(source_dir, copied)
    cutoff = datetime.combine(AS_OF, time.max, UTC)
    original = load_dataset_notes(copied, "CL-0003", cutoff, manifest.run_id)
    graph = build_data_flow(copied)
    first = invoke(graph, manifest, "CL-0003")
    path = copied / "rm_notes.json"
    notes = json.loads(path.read_text())
    note = next(item for item in notes if item["client_id"] == "CL-0003")
    note["note"] += " Client requests an additional meeting to discuss current priorities."
    path.write_text(json.dumps(notes), encoding="utf-8")
    pinned = load_dataset_notes(copied, "CL-0003", cutoff, manifest.run_id)
    current = load_dataset_notes(copied, "CL-0003", cutoff)
    assert pinned == original
    assert current.records != original.records
    unchanged = invoke(graph, manifest, "CL-0003")
    assert unchanged["pack_version"] == first["pack_version"]
    assert unchanged["processing_mode"] == "no_material_change"
    assert unchanged["status"] == "awaiting_review"


def test_every_client_bundle_and_claim_resolves_only_in_its_scope(published_sources):
    source_dir, manifest = published_sources
    graph = build_data_flow(source_dir)
    for client_id in manifest.client_ids:
        state = invoke(graph, manifest, client_id)
        bundle = CuratedClientBundle.model_validate(state["bundle"])
        pack = MeetingPack.model_validate(state["pack"])
        assert state["verification"]["passed"]
        assert all(
            evidence.record.get("client_id", client_id) == client_id
            for evidence in bundle.evidence.values()
        )
        assert all(
            record["client_id"] == client_id for record in state["connected_context"]["records"]
        )
        available = (
            {fact.id for fact in bundle.facts}
            | bundle.evidence.keys()
            | state["memory_index"]["chunks"].keys()
        )
        assert all(set(claim.citations) <= available for claim in pack.claims())
