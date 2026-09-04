"""Runtime acceptance through a compiled graph with explicitly injected test agents."""

import pytest

from app.pipeline.features import legacy_analytics
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.publish import read_latest
from app.pipeline.runner import DEFAULT_SOURCE_DIR, run_pipeline
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger


def analytics_stub(sources, run_id):
    result = legacy_analytics(sources, run_id)
    result.context_issues = []  # The deterministic test double explicitly supplies the contract.
    return result


def runtime(tmp_path, *, fail_client=None):
    calls = []
    verifications = []

    def context(state):
        return {}

    def wealth(state):
        calls.append((state["run_id"], state["client_id"]))
        if state["client_id"] == fail_client:
            raise RuntimeError("Generation failed")
        return {
            "draft_brief": {
                "sections": {
                    "summary": {"text": "Original", "citations": []},
                    "uncertainty": {"text": "Unknown", "citations": []},
                }
            }
        }

    def verifier(state):
        sections = state["meeting_brief"]["sections"]
        verifications.append(sections)
        passed = sections["summary"]["text"] != "invalid"
        return {"verification_report": {"passed": passed, "errors": [] if passed else ["invalid"]}}

    ledger = ReviewLedger(tmp_path / "ledger.sqlite")
    service = PipelineRuntime(
        ArtifactStore(tmp_path / "curated"),
        ledger,
        source_dir=DEFAULT_SOURCE_DIR,
        analytics=analytics_stub,
        agents=AgentHooks(context=context, wealth=wealth, verifier=verifier),
    )
    return service, calls, verifications


def test_seed_update_reuse_reset_and_retry_preserve_run_scoped_history(tmp_path):
    service, calls, _ = runtime(tmp_path)
    seed = service.seed()
    assert len(calls) == 20
    assert len(service.ledger.list_briefs(seed.run_id)) == 20
    service.seed()
    assert len(calls) == 20
    service.review(
        ReviewRequest(client_id="CL-0003", action="Approve", run_id=seed.run_id, brief_version=1)
    )
    update = service.update()
    assert calls[20:] == [(update.run_id, "CL-0003")]
    assert len(service.ledger.list_briefs(update.run_id)) == 20
    previous = service.ledger.get_brief("CL-0001", seed.run_id)
    reused = service.ledger.get_brief("CL-0001", update.run_id)
    assert previous is not None and reused is not None
    assert reused.body == previous.body
    assert service.ledger.list(update.run_id) == []
    service.update()
    assert len(calls) == 21
    assert len(service.ledger.list_briefs(update.run_id)) == 20
    assert service.reset().run_id == seed.run_id
    assert len(service.ledger.list(seed.run_id)) == 1
    assert len(service.ledger.list_briefs(update.run_id)) == 20


def test_edit_reverifies_synchronously_and_rejects_stale_or_failed_approval(tmp_path):
    service, _, verifications = runtime(tmp_path)
    seed = service.seed()
    result = service.review(
        ReviewRequest(
            client_id="CL-0003",
            action="Edit",
            run_id=seed.run_id,
            brief_version=1,
            section="summary",
            text="invalid",
        )
    )
    assert result["brief_version"] == 2
    assert result["verification_report"]["passed"] is False
    assert verifications[-1]["summary"]["text"] == "invalid"
    assert verifications[-1]["uncertainty"]["text"] == "Unknown"
    latest = service.ledger.get_brief("CL-0003", seed.run_id)
    assert latest is not None and latest.origin == "rm_edited"
    assert service.ledger.list(seed.run_id)[0].brief_version == 2
    with pytest.raises(ValueError, match="version"):
        service.review(
            ReviewRequest(
                client_id="CL-0003", action="Approve", run_id=seed.run_id, brief_version=1
            )
        )
    with pytest.raises(ValueError, match="verification"):
        service.review(
            ReviewRequest(
                client_id="CL-0003", action="Approve", run_id=seed.run_id, brief_version=2
            )
        )
    service.update()
    with pytest.raises(ValueError, match="run"):
        service.review(
            ReviewRequest(client_id="CL-0003", action="Reject", run_id=seed.run_id, brief_version=2)
        )


def test_prepare_current_registers_artifacts_and_only_generates_missing_outputs(tmp_path):
    service, calls, _ = runtime(tmp_path)
    seed = run_pipeline(curated_dir=service.store.root, analytics=analytics_stub, seed=True)
    assert service.ledger.get_run(seed.run_id) is None
    assert service.prepare_current() == seed
    assert len(calls) == 20
    assert service.prepare_current() == seed
    assert len(calls) == 20
    assert len(service.ledger.list_briefs(seed.run_id)) == 20


def test_prepare_current_without_run_does_nothing(tmp_path):
    service, calls, _ = runtime(tmp_path)
    assert service.prepare_current() is None
    assert calls == []


def test_first_seed_failure_does_not_expose_partial_active_run_and_retry_resumes(tmp_path):
    service, calls, _ = runtime(tmp_path, fail_client="CL-0003")
    with pytest.raises(RuntimeError, match="Generation failed"):
        service.seed()
    assert read_latest(service.store.root) is None
    run = service.ledger.list_runs()[0]
    assert len(service.ledger.list_briefs(run.run_id)) == 2
    recovered, recovered_calls, _ = runtime(tmp_path)
    seed = recovered.seed()
    assert seed.run_id == run.run_id
    assert len(recovered_calls) == 18
    assert recovered_calls[0] == (seed.run_id, "CL-0003")
    assert len(recovered.ledger.list_briefs(seed.run_id)) == 20


def test_failed_update_preserves_exact_previous_pointer(tmp_path):
    service, _, _ = runtime(tmp_path)
    seed = service.seed()
    pointer = (service.store.root / "latest.json").read_bytes()
    failing, _, _ = runtime(tmp_path, fail_client="CL-0003")
    with pytest.raises(RuntimeError, match="Generation failed"):
        failing.update()
    assert (service.store.root / "latest.json").read_bytes() == pointer
    assert service.store.load_manifest().run_id == seed.run_id


def test_runtime_instances_serialize_concurrent_generation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    first, first_calls, _ = runtime(tmp_path)
    second, second_calls, _ = runtime(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        one = executor.submit(first.seed)
        two = executor.submit(second.seed)
        first_run, second_run = one.result(), two.result()
    assert first_run.run_id == second_run.run_id
    assert len(first_calls) + len(second_calls) == 20
    assert len(first.ledger.list_briefs(first_run.run_id)) == 20


def test_reset_prepares_seed_missing_from_ledger_before_activating_it(tmp_path):
    service, calls, _ = runtime(tmp_path)
    seed = run_pipeline(curated_dir=service.store.root, analytics=analytics_stub, seed=True)
    update = run_pipeline(
        curated_dir=service.store.root,
        analytics=analytics_stub,
        overlay=DEFAULT_SOURCE_DIR / "fixtures/update",
    )
    assert seed.run_id != update.run_id
    service.prepare_current()
    assert len(service.ledger.list_briefs(seed.run_id)) == 0
    assert service.reset().run_id == seed.run_id
    assert len(service.ledger.list_briefs(seed.run_id)) == 20
    assert len(calls) == 40
