import shutil

import pandas as pd
from test_runtime import analytics_stub

from app.pipeline.evidence import evidence_id
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import DEFAULT_SOURCE_DIR
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.pipeline.view_model import build_view_model
from app.store import ReviewLedger


def test_unchanged_facts_reverify_old_claim_against_current_source_evidence(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(DEFAULT_SOURCE_DIR, source, ignore=shutil.ignore_patterns("generated"))
    generated = []
    events_path = source / "event_log.csv"
    events = pd.read_csv(events_path)
    cited_event = evidence_id("event_log", events.iloc[0])

    def wealth(state):
        generated.append(state["client_id"])
        citations = [cited_event] if state["client_id"] == "CL-0001" else []
        return {
            "draft_brief": {
                "sections": {"summary": {"text": "Discuss prior event.", "citations": citations}}
            }
        }

    def verifier(state):
        citations = state["meeting_brief"]["sections"]["summary"]["citations"]
        passed = all(identifier in state["evidence_map"] for identifier in citations)
        return {
            "verification_report": {"passed": passed, "errors": [] if passed else ["Missing event"]}
        }

    service = PipelineRuntime(
        ArtifactStore(tmp_path / "curated"),
        ReviewLedger(tmp_path / "ledger.sqlite"),
        source_dir=source,
        analytics=analytics_stub,
        agents=AgentHooks(wealth=wealth, verifier=verifier),
    )
    seed = service.seed()
    events.iloc[1:].to_csv(events_path, index=False)
    updated = service.update()
    assert service.store.load_change_report("CL-0001").processing_mode == "no_material_change"
    assert generated.count("CL-0001") == 1
    original = service.ledger.get_brief("CL-0001", seed.run_id)
    reused = service.ledger.get_brief("CL-0001", updated.run_id)
    assert original is not None and reused is not None
    assert original.verification_report["passed"] is True
    assert reused.verification_report["passed"] is False
    assert reused.verification_report["brief_version"] == 1
    model = build_view_model(service.store, service.ledger, source)
    assert model.clients["CL-0001"].meeting_brief is None


def test_section_edit_verifies_the_persisted_generation_envelope(tmp_path):
    seen = []
    connected = [{"record_id": "mail:1", "text": "Call me."}]
    memory = {"text": "Prefers calls.", "record_ids": ["mail:1"]}

    def context(state):
        return {"connected_context": connected, "memory_card": memory}

    def wealth(state):
        return {"draft_brief": {"sections": {"summary": {"text": "Original"}}}}

    def verifier(state):
        seen.append((state["connected_context"], state["memory_card"]))
        return {"verification_report": {"passed": True}}

    service = PipelineRuntime(
        ArtifactStore(tmp_path / "curated"),
        ReviewLedger(tmp_path / "ledger.sqlite"),
        analytics=analytics_stub,
        agents=AgentHooks(context=context, wealth=wealth, verifier=verifier),
    )
    seed = service.seed()
    result = service.review(
        ReviewRequest(
            run_id=seed.run_id,
            client_id="CL-0003",
            brief_version=1,
            action="Edit",
            section="summary",
            text="Updated",
        )
    )
    assert result["brief_version"] == 2
    assert seen[-1] == (connected, memory)
