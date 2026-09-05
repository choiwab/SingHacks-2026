"""Communication updates through the persisted runtime and API, without financial reruns."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_runtime import analytics_stub

from app.main import create_app
from app.mcp.connectors import replay_records
from app.pipeline.loaders import ArtifactStore
from app.pipeline.member2_bridge import member2_hooks
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger
from scripts.member_2_demo import FIXTURES


def setup_runtime(tmp_path):
    store = ArtifactStore(tmp_path / "curated")
    source = {"name": "initial", "calls": 0, "fail": False}
    verified = []

    def communications(client_id, as_of, revision):
        source["calls"] += 1
        if source["fail"]:
            raise OSError("Private connector failure details")
        return replay_records(
            FIXTURES / f"communications.{source['name']}.json",
            client_id=client_id,
            as_of=as_of,
        )

    def test_gate(state):
        # Explicit test provider exercises lifecycle, not financial verification.
        verified.append(state)
        return {"verification_report": {"passed": True, "errors": []}}

    agents = replace(member2_hooks(store, load_communications=communications), verifier=test_gate)
    service = PipelineRuntime(
        store,
        ReviewLedger(tmp_path / "ledger.sqlite"),
        analytics=analytics_stub,
        agents=agents,
    )
    return service, source, verified


def test_refresh_appends_only_changed_client_without_touching_financial_artifacts(tmp_path):
    service, source, verified = setup_runtime(tmp_path)
    seed = service.seed()
    original = service.ledger.get_brief("CL-0003", seed.run_id)
    assert original is not None
    review = ReviewRequest(
        client_id="CL-0003", run_id=seed.run_id, brief_version=1, action="Approve"
    )
    service.review(review)
    files = {p: p.read_bytes() for p in service.store.root.rglob("*.json")}
    source["name"] = "updated"
    calls, checks = source["calls"], len(verified)
    result = service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=1)
    assert result["changed"] is True
    assert result["run_id"] == seed.run_id and result["brief_version"] == 2
    assert source["calls"] == calls + 1
    assert len(verified) == checks + 1
    current = service.ledger.get_brief("CL-0003", seed.run_id)
    assert current is not None
    assert current.body["pack_version"] != original.body["pack_version"]
    assert current.body["communication_revision"] != original.body["communication_revision"]
    assert len(current.body["connected_context"]) > len(original.body["connected_context"])
    assert verified[-1]["pack"] == current.body["pack"]
    assert verified[-1]["connected_context"] == current.body["connected_context"]
    assert all(p.read_bytes() == content for p, content in files.items())
    assert len(service.ledger.list_briefs(seed.run_id)) == 21
    assert service.ledger.get_brief("CL-0003", seed.run_id, 1) == original
    assert not service.ledger.list(seed.run_id, client_id="CL-0003", brief_version=2)
    with pytest.raises(ValueError, match="no longer current"):
        service.review(review)
    unchanged = service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=2)
    assert unchanged["changed"] is False and unchanged["brief_version"] == 2
    assert len(verified) == checks + 1
    assert len(service.ledger.list_briefs(seed.run_id)) == 21


def test_api_refresh_deletion_failure_and_stale_requests_preserve_history(tmp_path):
    service, source, verified = setup_runtime(tmp_path)
    application = create_app(
        curated_dir=service.store.root,
        database=tmp_path / "ledger.sqlite",
        analytics=analytics_stub,
        agents=service.agents,
    )
    with TestClient(application) as client:
        initial = client.get("/api/app").json()
        initial_context = next(
            s["connected_context"] for s in verified if s["client_id"] == "CL-0003"
        )
        run_id = initial["run_id"]
        refresh = {"run_id": run_id, "brief_version": 1}
        path = "/api/clients/CL-0003/refresh"
        review = {"run_id": run_id, "client_id": "CL-0003", "brief_version": 1}
        assert client.post("/api/reviews", json={**review, "action": "Approve"}).status_code == 200
        source["name"] = "updated"
        result = client.post(path, json=refresh)
        assert result.status_code == 200, result.text
        assert result.json()["brief_version"] == 2
        assert client.get("/api/app").json()["clients"]["CL-0003"]["brief_status"] != "Ready"
        assert client.post(path, json=refresh).status_code == 409
        assert client.post("/api/reviews", json={**review, "action": "Approve"}).status_code == 409
        source["fail"] = True
        failed = client.post(path, json={**refresh, "brief_version": 2})
        assert failed.status_code == 502
        assert "Private" not in failed.text
        assert client.get("/api/app").json()["clients"]["CL-0003"]["brief_version"] == 2
        source["fail"] = False
        source["name"] = "initial"  # Deletes the newly cited record from the complete snapshot.
        removed = client.post(path, json={**refresh, "brief_version": 2})
        assert removed.status_code == 200 and removed.json()["brief_version"] == 3
        history = client.get("/api/clients/CL-0003/history").json()["versions"]
        assert [version["brief_version"] for version in history] == [3, 2, 1]
        assert history[0]["meeting_brief"] == history[2]["meeting_brief"]
        assert history[0]["reviews"] == [] and history[2]["reviews"][0]["action"] == "Approve"
        assert client.post(path, json={"run_id": "bad", "brief_version": 3}).status_code == 422
        assert client.post(path, json={"run_id": "f" * 12, "brief_version": 3}).status_code == 409
        assert client.post("/api/clients/CL-9999/refresh", json=refresh).status_code == 404
        assert verified[-1]["connected_context"] == initial_context


def test_reset_restores_seed_runs_latest_persisted_communication_revision(tmp_path):
    service, source, _ = setup_runtime(tmp_path)
    seed = service.seed()
    source["name"] = "updated"
    refreshed = service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=1)
    seed_brief = service.ledger.get_brief("CL-0003", seed.run_id)
    update = service.update()
    assert update.run_id != seed.run_id
    source["fail"] = True  # Reset and restart must not read mutable connector state.
    calls = source["calls"]
    restored = PipelineRuntime(
        service.store, ReviewLedger(tmp_path / "ledger.sqlite"), agents=service.agents
    )
    assert restored.reset().run_id == seed.run_id
    restored.prepare_current()
    assert source["calls"] == calls
    assert restored.ledger.get_brief("CL-0003", seed.run_id) == seed_brief
    assert refreshed["brief_version"] == 2
    assert restored.ledger.get_brief("CL-0003", update.run_id) is not None


def test_missing_full_verifier_keeps_refreshed_pack_unapprovable(tmp_path):
    service, source, _ = setup_runtime(tmp_path)
    assert service.agents is not None
    service.agents = replace(service.agents, verifier=None)
    seed = service.seed()
    source["name"] = "updated"
    result = service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=1)
    assert result["verification_report"]["passed"] is False
    with pytest.raises(ValueError, match="not passed verification"):
        service.review(
            ReviewRequest(
                client_id="CL-0003", run_id=seed.run_id, brief_version=2, action="Approve"
            )
        )


def test_failed_generation_does_not_cache_snapshot_and_can_retry(tmp_path):
    from app.pipeline.communications import CommunicationSnapshot
    from app.pipeline.runtime import CommunicationRefreshUnavailable

    service, source, _ = setup_runtime(tmp_path)
    seed = service.seed()
    source["name"] = "updated"
    hooks = service.agents
    assert hooks is not None
    original = service.ledger.get_brief("CL-0003", seed.run_id)

    def unavailable_candidate(state):
        snapshot = CommunicationSnapshot.model_validate(state["communication_snapshot"])
        return {
            "communication_revision": snapshot.revision,
            "meeting_brief": {},
            "context_issues": ["Context unavailable"],
        }

    service.agents = replace(hooks, generator=unavailable_candidate)
    with pytest.raises(CommunicationRefreshUnavailable, match="candidate unavailable"):
        service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=1)
    assert service.ledger.get_brief("CL-0003", seed.run_id) == original
    service.agents = hooks
    retried = service.refresh_communications("CL-0003", run_id=seed.run_id, brief_version=1)
    assert retried["changed"] is True and retried["brief_version"] == 2
