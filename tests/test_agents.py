"""Member 2 graph acceptance tests using explicit fixture data/gate boundaries."""

import socket
from copy import deepcopy
from datetime import date
from typing import Any

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.agents import generation
from app.agents.contracts import MeetingPack, VerificationIssue, VerificationReport
from app.agents.graph import build_agent_flow
from scripts.member_2_demo import (
    FIXTURES,
    demo_input,
    fixture_verifier,
    load_bundle,
    load_communications,
)


def make_graph(**kwargs: Any):
    return build_agent_flow(
        load_bundle=load_bundle,
        load_communications=load_communications,
        verify_pack=kwargs.pop("verify_pack", fixture_verifier),
        **kwargs,
    )


def config() -> RunnableConfig:
    return {"configurable": {"thread_id": "test"}}


def review(result, action="Approve", **kwargs):
    return Command(
        resume={
            "client_id": "CL-0003",
            "pack_version": result["pack_version"],
            "action": action,
            **kwargs,
        }
    )


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline tests must not make model requests")

    monkeypatch.setattr(generation, "request_narration", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def test_initial_pack_matches_golden_even_with_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    graph = make_graph()
    result = graph.invoke(demo_input(), config=config())
    expected = MeetingPack.model_validate_json((FIXTURES / "golden.initial.json").read_text())
    assert result["pack"] == expected.model_dump(mode="json")
    assert result["pack_version"] == expected.version
    assert result["__interrupt__"][0].value["pack"]["memory_card"] == result["pack"]["memory_card"]
    assert result["status"] == "awaiting_review"
    assert all(c.citations for c in expected.claims())
    assert len(expected.insights) <= 3


def test_joint_approval_edit_recheck_and_persistence_handoff():
    events = {}
    graph = make_graph(record_review=lambda event: events.update({event["event_id"]: event}))
    initial = graph.invoke(demo_input(), config=config())
    edited = graph.invoke(
        review(
            initial,
            "Edit",
            changes={"opening": "Could we start by discussing your priorities for this meeting?"},
        ),
        config=config(),
    )
    assert edited["pack_version"] != initial["pack_version"]
    assert edited["pack"]["brief"]["opening"]["authorship"] == "rm"
    assert edited["pack"]["memory_card"] == initial["pack"]["memory_card"]
    assert edited["__interrupt__"]
    approved = graph.invoke(review(edited), config=config())
    assert approved["last_approved"] == edited["pack"]
    assert approved["status"] == "approved"
    assert {event["action"] for event in events.values()} == {"Edit", "Approve"}


@pytest.mark.parametrize(
    "revision,kind",
    [("updated", "combined"), ("memory_only", "memory"), ("financial_only", "financial")],
)
def test_updates_require_new_approval_and_preserve_prior_pack(revision, kind):
    graph = make_graph()
    initial = graph.invoke(demo_input(), config=config())
    graph.invoke(review(initial), config=config())
    result = graph.invoke(demo_input(revision), config=config())
    assert result["processing_mode"] == "incremental_update"
    assert result["change_kind"] == kind
    assert result["pack_version"] != initial["pack_version"]
    assert result["last_approved"] == initial["pack"]
    assert result["__interrupt__"]
    if revision == "memory_only":
        assert result["bundle"] == initial["bundle"]
        assert [i["score"] for i in result["insights"]] == [i["score"] for i in initial["insights"]]
        conflicts = [
            c for c in result["pack"]["brief"]["uncertainty"] if c["id"].startswith("conflict:")
        ]
        assert len(conflicts) == 1
        assert len(conflicts[0]["citations"]) == 2


@pytest.mark.parametrize("action,expected", [("Approve", "approved"), ("Reject", "rejected")])
def test_unchanged_preserves_actual_status(action, expected):
    graph = make_graph()
    initial = graph.invoke(demo_input(), config=config())
    graph.invoke(review(initial, action), config=config())
    result = graph.invoke(demo_input(), config=config())
    assert result["processing_mode"] == "no_material_change"
    assert result["pack_version"] == initial["pack_version"]
    assert result["status"] == expected
    assert not result.get("__interrupt__")


def test_failed_verification_never_reaches_review_and_retains_previous():
    def verifier(pack, bundle, connected):
        if bundle.version.endswith("updated"):
            return VerificationReport(
                pack_version=pack.version,
                passed=False,
                issues=[VerificationIssue(claim_id="opening", reason="Unverified")],
            )
        return fixture_verifier(pack, bundle, connected)

    graph = make_graph(verify_pack=verifier)
    initial = graph.invoke(demo_input(), config=config())
    graph.invoke(review(initial), config=config())
    failed = graph.invoke(demo_input("updated"), config=config())
    assert failed["status"] == "needs_confirmation"
    assert not failed.get("__interrupt__")
    assert failed["last_approved"] == initial["pack"]
    assert "opening: Unverified" in failed["issues"]


def test_stale_approval_and_read_only_edits_are_rejected():
    graph = make_graph()
    initial = graph.invoke(demo_input(), config=config())
    stale = graph.invoke(
        Command(resume={"client_id": "CL-0003", "pack_version": "stale", "action": "Approve"}),
        config=config(),
    )
    assert "stale" in stale["__interrupt__"][0].value["validation_error"]
    invalid = graph.invoke(
        review(initial, "Edit", changes={"memory": "replace facts"}), config=config()
    )
    assert "Only the opening" in invalid["__interrupt__"][0].value["validation_error"]
    assert invalid["pack"] == initial["pack"]
    approved = graph.invoke(review(initial), config=config())
    assert approved["status"] == "approved"


def test_correction_flag_leaves_content_unchanged():
    graph = make_graph()
    initial = graph.invoke(demo_input(), config=config())
    claim_id = initial["pack"]["memory_card"]["who_they_are"]["claims"][0]["id"]
    result = graph.invoke(
        review(initial, "Flag", claim_id=claim_id, reason="Confirm this with client"),
        config=config(),
    )
    assert result["pack"] == initial["pack"]
    assert result["status"] == "needs_confirmation"
    assert result["review_events"][-1]["claim_id"] == claim_id


def test_wrong_client_and_quality_issues_stop_context():
    graph = make_graph()
    result = graph.invoke({**demo_input(), "client_id": "CL-9999"}, config=config())
    assert result["status"] == "needs_confirmation"
    assert all(event["node"] != "wealth" for event in result["trace"])


def test_provider_failures_fall_back_and_valid_structured_text_reaches_gate(monkeypatch):
    pack = MeetingPack.model_validate_json((FIXTURES / "golden.initial.json").read_text())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert generation.generate(pack, evidence={}, live=True)[1] == "fallback:missing_configuration"
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    def timeout(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(generation, "request_narration", timeout)
    assert generation.generate(pack, evidence={}, live=True)[0] == pack
    monkeypatch.setattr(generation, "request_narration", lambda *a, **k: [])
    assert generation.generate(pack, evidence={}, live=True)[1].startswith("fallback:")
    monkeypatch.setattr(
        generation, "request_narration", lambda *a, **k: {"status": "completed", "output": []}
    )
    assert generation.generate(pack, evidence={}, live=True)[1].startswith("fallback:")
    import json

    claims = [pack.brief.opening, *pack.brief.talking_points, *pack.brief.questions]
    wording = [{"claim_id": c.id, "text": c.text} for c in claims]
    wording[0]["text"] = "Unverified generated opening"

    def response(payload, **kwargs):
        assert payload["text"]["format"]["strict"] is True
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps({"wording": wording})}],
                }
            ],
        }

    monkeypatch.setattr(generation, "request_narration", response)
    generated, note = generation.generate(pack, evidence={}, live=True)
    assert note == "openai"
    assert generated.memory_card == pack.memory_card
    assert generated.insights == pack.insights
    graph = make_graph(live_generation=True)
    result = graph.invoke(demo_input(), config=config())
    assert result["status"] == "needs_confirmation"
    assert not result.get("__interrupt__")


def test_verifier_cannot_mutate_candidate():
    def mutate(pack, bundle, connected):
        before = pack.version
        pack.brief.opening.text = "Overwritten"
        return VerificationReport(pack_version=before, passed=True)

    result = make_graph(verify_pack=mutate).invoke(demo_input(), config=config())
    assert result["pack"]["brief"]["opening"]["text"] != "Overwritten"


def test_packs_and_facts_are_not_mutated_by_generation():
    original = load_bundle("CL-0003", date(2026, 8, 26), "initial")
    before = deepcopy(original.model_dump(mode="json"))
    result = make_graph().invoke(demo_input(), config=config())
    assert result["bundle"] == before


def test_context_recovers_after_transient_quality_failure():
    broken = False

    def loader(*args):
        bundle = load_bundle(*args)
        if broken:
            bundle.quality_issues = ["Source snapshot incomplete"]
        return bundle

    graph = build_agent_flow(
        load_bundle=loader,
        load_communications=load_communications,
        verify_pack=fixture_verifier,
    )
    initial = graph.invoke(demo_input(), config=config())
    graph.invoke(review(initial), config=config())
    broken = True
    failed = graph.invoke(demo_input(), config=config())
    assert failed["status"] == "needs_confirmation"
    assert failed["last_approved"] == initial["pack"]
    broken = False
    recovered = graph.invoke(demo_input(), config=config())
    assert recovered["issues"] == []
    assert recovered["status"] == "awaiting_review"
    assert recovered["__interrupt__"]


def test_update_supersedes_pending_pack_and_rejects_its_approval():
    graph = make_graph()
    initial = graph.invoke(demo_input(), config=config())
    updated = graph.invoke(demo_input("updated"), config=config())
    assert updated["pack_version"] != initial["pack_version"]
    stale = graph.invoke(review(initial), config=config())
    assert "stale" in stale["__interrupt__"][0].value["validation_error"]
    approved = graph.invoke(review(updated), config=config())
    assert approved["last_approved"] == updated["pack"]


def test_stale_verifier_report_fails_closed():
    graph = make_graph(
        verify_pack=lambda *args: VerificationReport(pack_version="stale", passed=True)
    )
    result = graph.invoke(demo_input(), config=config())
    assert result["status"] == "needs_confirmation"
    assert not result.get("__interrupt__")


def test_persistence_failure_does_not_finalize_approval():
    def unavailable(event):
        raise OSError("Review store unavailable")

    graph = make_graph(record_review=unavailable)
    initial = graph.invoke(demo_input(), config=config())
    with pytest.raises(OSError, match="Review store unavailable"):
        graph.invoke(review(initial), config=config())
    state = graph.get_state(config()).values
    assert state["status"] != "approved"
    assert state.get("last_approved") is None
