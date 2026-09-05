"""Production publication, cache safety and downstream contract checks."""

from datetime import date

import pytest

from app.pipeline.agent_projection import project_agent_bundle
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import run_pipeline


def test_phase_a_is_default_and_all_clients_have_resolvable_artifacts(tmp_path):
    manifest = run_pipeline(curated_dir=tmp_path)
    store = ArtifactStore(tmp_path)
    evidence = store.load_evidence_map(run_id=manifest.run_id)
    assert len(manifest.client_ids) == 20
    assert ":phase-a:" in manifest.pipeline_version
    for client_id in manifest.client_ids:
        facts = store.load_fact_bundle(client_id).facts
        signals = store.load_signal_set(client_id).signals
        assert facts
        assert all(fact.formula_id.startswith("phase-a-") for fact in facts)
        assert all(fact.id.startswith(f"{client_id}:fact:") for fact in facts)
        fact_ids = {fact.id for fact in facts}
        for item in [*facts, *signals]:
            assert item.evidence_ids and set(item.evidence_ids) <= evidence.entries.keys()
        assert all(set(signal.fact_ids) <= fact_ids for signal in signals)
        projected = project_agent_bundle(store, client_id, manifest.run_id)
        assert projected.facts == facts
        assert len(projected.signals) == len(signals)
        assert not projected.quality_issues
    assert store.load_signal_set("CL-0003").signals


def test_cached_inputs_skip_csv_ingest_and_preserve_artifacts(tmp_path, monkeypatch):
    import app.pipeline.runner as runner

    first = run_pipeline(curated_dir=tmp_path)

    def unexpected(*args, **kwargs):
        pytest.fail("Unchanged inputs must not repeat ingest or analytics")

    monkeypatch.setattr(runner, "ingest_sources", unexpected)
    assert run_pipeline(curated_dir=tmp_path) == first


def test_policy_revision_invalidates_cache(tmp_path, monkeypatch):
    import app.pipeline.runner as runner

    first = run_pipeline(curated_dir=tmp_path)
    original = runner.analytics_version
    monkeypatch.setattr(runner, "analytics_version", lambda version: original(version) + "-review")
    second = run_pipeline(curated_dir=tmp_path)
    assert second.run_id != first.run_id


def test_fact_methodology_change_routes_update_even_if_value_is_unchanged():
    from app.pipeline.changes import compare_client
    from app.pipeline.schemas import Fact, FactBundle, SignalSet

    as_of = date(2026, 8, 26)
    fact = Fact(
        id="CL-0003:fact:example",
        client_id="CL-0003",
        kind="example",
        value=1,
        unit="number",
        formula_id="original",
        evidence_ids=["clients:CL-0003"],
        as_of=as_of,
        confidence=1,
    )
    before = FactBundle(client_id="CL-0003", as_of=as_of, facts=[fact])
    after = before.model_copy(deep=True)
    after.facts[0].formula_id = "reviewed"
    signals = SignalSet(client_id="CL-0003", as_of=as_of)
    report = compare_client(after, signals, before, signals, changed_source_files=[])
    assert report.processing_mode == "incremental_update"
    assert report.changed_fact_ids == [fact.id]


@pytest.mark.parametrize("as_of", [date(2026, 2, 27), date(2026, 6, 30)])
def test_historical_default_runs_publish_without_future_evidence(tmp_path, as_of):
    manifest = run_pipeline(curated_dir=tmp_path, as_of=as_of)
    evidence = ArtifactStore(tmp_path).load_evidence_map(run_id=manifest.run_id)
    for entry in evidence.entries.values():
        for key in ("snapshot_date", "event_date", "note_date", "trade_date"):
            if entry.record.get(key):
                assert str(entry.record[key]) <= as_of.isoformat()
    assert any("not effective" in issue for issue in manifest.context_issues)
