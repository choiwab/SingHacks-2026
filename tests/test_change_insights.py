"""Persisted comparison metadata reaches the visible insight change label."""

from test_changes import facts, signals
from test_loaders import CLIENT, SEED
from test_view_model import rewrite, setup_projection, store_brief

from app.pipeline.changes import compare_client
from app.pipeline.loaders import ArtifactStore
from app.pipeline.view_model import build_view_model


def test_allocation_movement_marks_same_severity_insight_changed(tmp_path):
    root, run, source, ledger = setup_projection(tmp_path)
    old_signals = signals("prior", {"mandate": "high"})
    old_signals.signals[0].fact_ids = ["allocation"]
    new_signals = old_signals.model_copy(update={"run_id": SEED})
    report = compare_client(
        facts(SEED, {"allocation": 80}),
        new_signals,
        facts("prior", {"allocation": 71.5}),
        old_signals,
        changed_source_files=["holdings.csv"],
    )
    rewrite(run / "change_report" / f"{CLIENT}.json", **report.model_dump(mode="json"))
    store_brief(
        ledger,
        body={
            "meeting_brief": {"sections": {"summary": {"text": "Discuss allocation"}}},
            "insights": [{"signal_id": "mandate", "text": "Allocation increased"}],
        },
    )
    client = build_view_model(ArtifactStore(root), ledger, source).clients[CLIENT]
    assert client.insights[0]["change_status"] == "Changed"
