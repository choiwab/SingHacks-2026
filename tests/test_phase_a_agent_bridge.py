"""The existing artifact runtime consumes the same agents and rechecks human decisions."""

from copy import deepcopy

import pytest

from app.agents.wording import ALTERNATE_OPENING
from app.pipeline.agent_bridge import phase_a_hooks
from app.pipeline.graph_adapter import verify_brief
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger


@pytest.fixture()
def wired_runtime(tmp_path):
    store = ArtifactStore(tmp_path / "curated")
    ledger = ReviewLedger(tmp_path / "reviews.sqlite3")
    runtime = PipelineRuntime(store, ledger, agents=phase_a_hooks(store))
    yield runtime
    ledger.close()


def test_existing_pipeline_runtime_generates_verified_candidates_without_approval(wired_runtime):
    runtime = wired_runtime
    seed = runtime.seed()
    assert len(seed.client_ids) == 20
    for client_id in seed.client_ids:
        brief = runtime.ledger.get_brief(client_id, seed.run_id)
        assert brief.verification_report["passed"]
        assert brief.body["pack"]["generation_mode"] == "deterministic"
        assert brief.body["information_requests"] == brief.body["pack"]["information_requests"]
    assert runtime.ledger.list(run_id=seed.run_id) == []
    repeated = runtime.seed()
    assert repeated.run_id == seed.run_id
    assert runtime.ledger.get_brief("CL-0003", seed.run_id).brief_version == 1


@pytest.mark.parametrize("field", ["meeting_brief", "information_requests", "memory_card"])
def test_shadow_projection_tampering_fails_verification(wired_runtime, field):
    runtime = wired_runtime
    seed = runtime.seed()
    brief = runtime.ledger.get_brief("CL-0003", seed.run_id)
    body = deepcopy(brief.body)
    body[field] = [] if field == "information_requests" else {}
    report = verify_brief(
        runtime.store, "CL-0003", seed.run_id, body, verifier=runtime.agents.verifier
    )
    assert not report["passed"]


def test_edit_and_approval_recheck_current_policy(wired_runtime, monkeypatch):
    import app.pipeline.agent_bridge as bridge

    runtime = wired_runtime
    seed = runtime.seed()
    result = runtime.review(
        ReviewRequest(
            client_id="CL-0003",
            run_id=seed.run_id,
            brief_version=1,
            action="Edit",
            section="opening",
            text=ALTERNATE_OPENING,
        )
    )
    assert result["verification_report"]["passed"]
    monkeypatch.setattr(bridge, "generation_policy_version", lambda: "changed-policy")
    with pytest.raises(ValueError, match="not passed verification"):
        runtime.review(
            ReviewRequest(
                client_id="CL-0003",
                run_id=seed.run_id,
                brief_version=2,
                action="Approve",
            )
        )
    assert all(item.action != "Approve" for item in runtime.ledger.list(run_id=seed.run_id))
    runtime.prepare_current()
    refreshed = runtime.ledger.get_brief("CL-0003", seed.run_id)
    assert refreshed.brief_version == 3
    assert refreshed.verification_report["passed"]


def test_updated_run_reuses_only_verified_unchanged_candidates(wired_runtime):
    runtime = wired_runtime
    seed = runtime.seed()
    updated = runtime.update()
    assert seed.run_id != updated.run_id
    for client_id in updated.client_ids:
        assert runtime.ledger.get_brief(client_id, updated.run_id).verification_report["passed"]
    runtime.reset()
    assert runtime.store.load_manifest().run_id == seed.run_id
