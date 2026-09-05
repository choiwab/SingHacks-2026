"""The generation graph reads a pinned run and never claims absent capabilities."""

from test_loaders import CLIENT, SEED, UPDATE, publish_fixture

from app.pipeline.graph_adapter import AgentHooks, execute_client, verify_brief
from app.pipeline.loaders import ArtifactStore


def test_default_graph_discloses_unconnected_agents_and_incomplete_verification(tmp_path):
    publish_fixture(tmp_path)
    result = execute_client(ArtifactStore(tmp_path), CLIENT, SEED)
    assert "Agent generation is not connected" in result["context_issues"]
    assert result["insights"] == []
    assert result["memory_card"] is None
    assert result["connected_context"] == []
    assert not any(result["meeting_brief"]["sections"].values())
    report = result["verification_report"]
    assert report["passed"] is False
    assert report["verification_scope"] == "citation_existence_only"
    assert report["brief_version"] == 1


def test_injected_agents_see_pinned_artifacts_and_graph_finishes_without_review_interrupt(tmp_path):
    publish_fixture(tmp_path, SEED)
    publish_fixture(tmp_path, UPDATE)
    calls = []

    def context(state):
        calls.append("context")
        assert state["run_id"] == SEED
        assert state["evidence_map"]["rm_notes:N-005"]["record"]["note"] == SEED
        return {"memory_card": {"who_they_are": "client"}, "connected_context": []}

    def wealth(state):
        calls.append("wealth")
        assert state["client_context"]["client_id"] == CLIENT
        return {
            "ranked_insights": [{"text": "Example", "citations": ["rm_notes:N-005"]}],
            "draft_brief": {
                "sections": {"summary": [{"text": "Example", "citations": ["rm_notes:N-005"]}]}
            },
        }

    def verify(state):
        calls.append("verify")
        assert state["meeting_brief"]["sections"]["summary"][0]["text"] == "Example"
        return {"verification_report": {"passed": True, "errors": []}}

    result = execute_client(
        ArtifactStore(tmp_path),
        CLIENT,
        SEED,
        agents=AgentHooks(context=context, wealth=wealth, verifier=verify),
    )
    assert calls == ["context", "wealth", "verify"]
    assert result["verification_report"]["passed"]
    assert result["memory_card"] == {"who_they_are": "client"}
    assert len(result["insights"]) == 1


def test_edit_reverification_scans_entire_brief_and_tracks_version(tmp_path):
    publish_fixture(tmp_path)
    envelope = {
        "meeting_brief": {
            "sections": {
                "summary": [{"text": "Cited", "citations": ["rm_notes:N-005"]}],
                "uncertainty": [{"text": "Uncited"}],
                "discussion_topics": [{"text": "Unknown", "citations": ["missing:evidence"]}],
            }
        }
    }
    result = verify_brief(ArtifactStore(tmp_path), CLIENT, SEED, envelope, brief_version=2)
    assert result["passed"] is False
    assert result["brief_version"] == 2
    assert any("no citation" in error for error in result["errors"])
    assert "unresolved citation: missing:evidence" in result["errors"]


def test_manifest_context_issues_reach_generation_result(tmp_path):
    import json

    publish_fixture(tmp_path)
    manifest_path = tmp_path / "runs" / SEED / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["context_issues"] = ["Analytics signal definitions are pending"]
    manifest_path.write_text(json.dumps(manifest))
    result = execute_client(ArtifactStore(tmp_path), CLIENT, SEED)
    assert "Analytics signal definitions are pending" in result["context_issues"]


def test_full_evidence_registry_is_pinned_to_requested_run(tmp_path, monkeypatch):
    from app.pipeline.loaders import load_evidence_map

    publish_fixture(tmp_path, SEED)
    publish_fixture(tmp_path, UPDATE)
    monkeypatch.setenv("PIPELINE_CURATED_DIR", str(tmp_path))
    evidence = load_evidence_map(run_id=SEED)
    assert evidence.run_id == SEED
    assert evidence.entries["rm_notes:N-005"].record["note"] == SEED


def test_reverification_preserves_stored_connector_and_memory_context(tmp_path):
    publish_fixture(tmp_path)
    connected = [{"record_id": "mail:1", "connector": "mail", "text": "Client wants a call."}]
    memory = {"communication": {"text": "Prefers calls.", "record_ids": ["mail:1"]}}
    envelope = {
        "meeting_brief": {"sections": {"summary": {"text": "Call the client."}}},
        "connected_context": connected,
        "memory_card": memory,
        "insights": [{"text": "Discuss preferences."}],
        "context_issues": ["Cached mail"],
    }

    def verifier(state):
        assert state["run_id"] == SEED
        assert state["connected_context"] == connected
        assert state["memory_card"] == memory
        assert state["ranked_insights"] == envelope["insights"]
        assert "Cached mail" in state["context_issues"]
        return {"verification_report": {"passed": True}}

    assert (
        verify_brief(
            ArtifactStore(tmp_path), CLIENT, SEED, envelope, verifier=verifier, brief_version=2
        )["brief_version"]
        == 2
    )
