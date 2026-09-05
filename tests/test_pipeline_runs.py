import shutil
from datetime import date
from pathlib import Path

import pytest

from app.pipeline.features import FeatureArtifacts
from app.pipeline.loaders import ArtifactStore
from app.pipeline.publish import read_latest, reset_latest
from app.pipeline.runner import DEFAULT_SOURCE_DIR, run_pipeline
from app.pipeline.schemas import FactBundle, SignalSet
from app.pipeline.stages.validate import QualityValidationError


def test_publish_book_is_byte_identical_and_update_changes_only_margarethe_deadline(tmp_path):
    seed = run_pipeline(curated_dir=tmp_path, seed=True)
    before = {
        str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob("*.json")
    }
    repeated = run_pipeline(curated_dir=tmp_path, seed=True)
    assert seed == repeated
    assert before == {
        str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob("*.json")
    }
    updated = run_pipeline(curated_dir=tmp_path, overlay=DEFAULT_SOURCE_DIR / "fixtures/update")
    store = ArtifactStore(tmp_path)
    assert len(updated.client_ids) == 20
    changed = {
        client: store.load_change_report(client).changed_fact_ids
        for client in updated.client_ids
        if store.load_change_report(client).changed_fact_ids
    }
    assert changed == {"CL-0003": ["CL-0003:fact:deadline:days"]}
    facts = {fact.id: fact.value for fact in store.load_fact_bundle("CL-0003").facts}
    assert facts["CL-0003:fact:mandate-gap:actual_pct"] == 71.5
    assert facts["CL-0003:fact:mandate-gap:limit_pct"] == 30
    assert facts["CL-0003:fact:deadline:days"] == 6
    reset_latest(tmp_path)
    pointer = read_latest(tmp_path)
    assert pointer is not None and pointer["run_id"] == seed.run_id
    assert store.load_manifest(updated.run_id).run_id == updated.run_id


def test_invalid_sources_never_replace_latest(tmp_path):
    source = tmp_path / "sources"
    shutil.copytree(DEFAULT_SOURCE_DIR, source, ignore=shutil.ignore_patterns("generated"))
    root = tmp_path / "curated"
    run_pipeline(source_dir=source, curated_dir=root, seed=True)
    before = (root / "latest.json").read_bytes()
    (source / "holdings.csv").write_text("invalid\n")
    with pytest.raises(QualityValidationError):
        run_pipeline(source_dir=source, curated_dir=root)
    assert (root / "latest.json").read_bytes() == before
    assert len(list((root / "runs").iterdir())) == 1


def test_historical_artifacts_never_include_future_observations(tmp_path):
    def analytics(sources, run_id):
        return FeatureArtifacts(
            {
                client: FactBundle(client_id=client, run_id=run_id, as_of=sources.as_of)
                for client in sources.clients
            },
            {
                client: SignalSet(client_id=client, run_id=run_id, as_of=sources.as_of)
                for client in sources.clients
            },
            [],
        )

    run = run_pipeline(curated_dir=tmp_path, as_of=date(2026, 6, 30), analytics=analytics)
    for path in (tmp_path / "runs" / run.run_id).rglob("*.json"):
        if path.name == "manifest.json":
            continue
        assert "2026-08-26" not in path.read_text(), path
    bundle = ArtifactStore(tmp_path).load_curated_bundle("CL-0003")
    assert bundle.cash_needs[0].due_from == date(2026, 10, 1)


def test_artifacts_do_not_depend_on_source_directory(tmp_path):
    copied = tmp_path / "copy"
    shutil.copytree(DEFAULT_SOURCE_DIR, copied, ignore=shutil.ignore_patterns("generated"))
    original = run_pipeline(curated_dir=tmp_path / "a")
    duplicate = run_pipeline(source_dir=copied, curated_dir=tmp_path / "b")
    assert original.run_id == duplicate.run_id
    for path in (tmp_path / "a/runs" / original.run_id).rglob("*.json"):
        if path.name != "manifest.json":
            counterpart = tmp_path / "b" / path.relative_to(tmp_path / "a")
            assert path.read_bytes() == counterpart.read_bytes(), path


def _test_analytics(sources, run_id):
    from app.pipeline.schemas import Fact

    bundles = {
        client: FactBundle(client_id=client, run_id=run_id, as_of=sources.as_of)
        for client in sources.clients
    }
    bundles["CL-0003"].facts = [
        Fact(
            id="test-fact",
            client_id="CL-0003",
            kind="test",
            value=1,
            unit="number",
            formula_id="test-fixture",
            evidence_ids=["clients:CL-0003"],
            as_of=sources.as_of,
            confidence=1,
        )
    ]
    return FeatureArtifacts(
        bundles,
        {
            client: SignalSet(client_id=client, run_id=run_id, as_of=sources.as_of)
            for client in sources.clients
        },
        [],
    )


def test_pipeline_version_change_does_not_short_circuit_fact_diff(tmp_path):
    run_pipeline(curated_dir=tmp_path, analytics=_test_analytics, pipeline_version="test-v1")

    def changed(sources, run_id):
        result = _test_analytics(sources, run_id)
        result.facts["CL-0003"].facts[0].value = 2
        return result

    run_pipeline(curated_dir=tmp_path, analytics=changed, pipeline_version="test-v2")
    report = ArtifactStore(tmp_path).load_change_report("CL-0003")
    assert report.changed_fact_ids == ["test-fact"]
    assert report.processing_mode == "incremental_update"


@pytest.mark.parametrize(
    "defect",
    [
        "fact_client",
        "fact_date",
        "bundle_run",
        "signal_client",
        "signal_date",
        "signal_reference",
        "duplicate_fact",
    ],
)
def test_invalid_nested_analytics_outputs_never_publish(tmp_path, defect):
    from app.pipeline.schemas import Signal

    def malformed(sources, run_id):
        result = _test_analytics(sources, run_id)
        bundle = result.facts["CL-0003"]
        fact = bundle.facts[0]
        signals = result.signals["CL-0003"]
        signals.signals = [
            Signal(
                id="test-signal",
                client_id="CL-0003",
                kind="test",
                severity="low",
                priority_score=0,
                fact_ids=["test-fact"],
                as_of=sources.as_of,
            )
        ]
        if defect == "fact_client":
            fact.client_id = "CL-0004"
        elif defect == "fact_date":
            fact.as_of = date(2026, 8, 27)
        elif defect == "bundle_run":
            bundle.run_id = "wrong-run"
        elif defect == "signal_client":
            signals.signals[0].client_id = "CL-0004"
        elif defect == "signal_date":
            signals.signals[0].as_of = date(2026, 8, 27)
        elif defect == "signal_reference":
            signals.signals[0].fact_ids = ["missing-fact"]
        else:
            bundle.facts.append(fact.model_copy())
        return result

    with pytest.raises(ValueError, match="Analytics"):
        run_pipeline(curated_dir=tmp_path, analytics=malformed, pipeline_version="test-bad")
    assert not (tmp_path / "latest.json").exists()


def test_overlay_mutation_during_analytics_never_publishes(tmp_path):
    overlay = tmp_path / "overlay"
    shutil.copytree(DEFAULT_SOURCE_DIR / "fixtures/update", overlay)

    def mutate(sources, run_id):
        result = _test_analytics(sources, run_id)
        target = overlay / "planned_cash_needs.csv"
        target.write_text(target.read_text().replace("2026-09-01", "2026-09-02"))
        return result

    with pytest.raises(ValueError, match="Overlay files changed"):
        run_pipeline(
            curated_dir=tmp_path / "curated",
            overlay=overlay,
            analytics=mutate,
            pipeline_version="test-race",
        )
    assert not (tmp_path / "curated/latest.json").exists()


def test_staged_run_and_cached_retry_leave_latest_unchanged(tmp_path):
    seed = run_pipeline(curated_dir=tmp_path, seed=True)
    pointer = (tmp_path / "latest.json").read_bytes()
    staged = run_pipeline(
        curated_dir=tmp_path, overlay=DEFAULT_SOURCE_DIR / "fixtures/update", activate=False
    )
    assert ArtifactStore(tmp_path).load_manifest(staged.run_id).run_id == staged.run_id
    assert staged.run_id != seed.run_id
    assert (tmp_path / "latest.json").read_bytes() == pointer
    assert (
        run_pipeline(
            curated_dir=tmp_path, overlay=DEFAULT_SOURCE_DIR / "fixtures/update", activate=False
        )
        == staged
    )
    assert (tmp_path / "latest.json").read_bytes() == pointer


def test_source_mutation_between_fingerprint_and_ingest_is_detected(tmp_path, monkeypatch):
    source = tmp_path / "source"
    shutil.copytree(DEFAULT_SOURCE_DIR, source, ignore=shutil.ignore_patterns("generated"))
    target = source / "clients.csv"
    read_bytes = Path.read_bytes
    changed = False

    def mutate_after_hash_read(path):
        nonlocal changed
        raw = read_bytes(path)
        if path == target and not changed:
            changed = True
            path.write_bytes(raw.replace(b"Hartono Wijaya Kusuma", b"Hartono W. Kusuma"))
        return raw

    monkeypatch.setattr(Path, "read_bytes", mutate_after_hash_read)
    with pytest.raises(ValueError, match="Source files changed"):
        run_pipeline(
            source_dir=source,
            curated_dir=tmp_path / "curated",
            analytics=_test_analytics,
            pipeline_version="test-race",
        )
    assert not (tmp_path / "curated/latest.json").exists()


def test_runner_passes_filtered_sources_through_each_normalization_hook(tmp_path):
    calls = []

    def fx(tables, as_of):
        assert tables["holdings"]["snapshot_date"].max() == "2026-06-30"
        calls.append("fx")
        return tables

    def bond(tables, as_of):
        calls.append("bond")
        return tables

    def lookthrough(tables, as_of):
        calls.append("lookthrough")
        return tables

    run = run_pipeline(
        curated_dir=tmp_path,
        as_of=date(2026, 6, 30),
        analytics=_test_analytics,
        pipeline_version="test-hooks",
        normalize_fx=fx,
        normalize_bond_nominal=bond,
        look_through=lookthrough,
    )
    assert calls == ["fx", "bond", "lookthrough"]
    assert len(run.client_ids) == 20


@pytest.mark.parametrize("overlaid", [False, True])
def test_normalization_keeps_raw_evidence_and_normalized_bundle(tmp_path, overlaid):
    overlay = None
    if overlaid:
        overlay = tmp_path / "overlay"
        overlay.mkdir()
        lines = (DEFAULT_SOURCE_DIR / "holdings.csv").read_text().splitlines()
        (overlay / "holdings.csv").write_text("\n".join(lines[:2]) + "\n")

    def normalize(tables, as_of):
        tables["holdings"].loc[0, "market_value_base"] = 16904160
        return tables

    run_pipeline(
        curated_dir=tmp_path,
        analytics=_test_analytics,
        pipeline_version="test-raw-evidence",
        normalize_fx=normalize,
        overlay=overlay,
    )
    store = ArtifactStore(tmp_path)
    entry = store.load_evidence_map().entries["holdings:2025-12-31:PF-0001:SYN-EQ-0001"]
    assert entry.record["market_value_base"] == 8452080
    assert entry.fields["market_value_base"] == 8452080
    assert (entry.source_file, entry.row_index) == (
        "fixtures/update/holdings.csv" if overlaid else "holdings.csv",
        2,
    )
    holding = store.load_curated_bundle("CL-0001").holdings[0]
    assert holding.market_value_base == 16904160
