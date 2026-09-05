from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.pipeline.publish import (
    PIPELINE_VERSION,
    compute_run_id,
    publish_run,
    read_latest,
    reset_latest,
)
from app.pipeline.schemas import (
    ChangeReport,
    ClientProfile,
    ContractModel,
    CuratedClientBundle,
    DataQualityFinding,
    DataQualityReport,
    EvidenceMap,
    FactBundle,
    RunManifest,
    SignalSet,
)

AS_OF = date(2026, 8, 26)


def manifest(*, source_hash: str = "seed", overlay: bool = False) -> RunManifest:
    sources = {"clients.csv": source_hash}
    overlays = {"rm_notes.json": "update"} if overlay else {}
    return RunManifest(
        as_of=AS_OF,
        run_id=compute_run_id(AS_OF, sources, overlays),
        pipeline_version=PIPELINE_VERSION,
        git_sha="not-part-of-identity",
        source_hashes=sources,
        overlay_hashes=overlays,
        client_ids=["CL-0003"],
        created_at=datetime(2026, 9, 5, tzinfo=UTC),
    )


def files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def artifacts(run: RunManifest) -> dict[str, ContractModel]:
    import csv

    with (Path(__file__).resolve().parents[1] / "data/clients.csv").open() as handle:
        row = next(row for row in csv.DictReader(handle) if row["client_id"] == "CL-0003")
    profile = ClientProfile.model_validate(row)
    envelope = {"as_of": run.as_of, "run_id": run.run_id}
    return {
        "data_quality_report.json": DataQualityReport(**envelope),
        "evidence_map.json": EvidenceMap(**envelope),
        "curated_client_bundle/CL-0003.json": CuratedClientBundle(
            **envelope, client_id="CL-0003", profile=profile
        ),
        "fact_bundle/CL-0003.json": FactBundle(**envelope, client_id="CL-0003"),
        "signal_set/CL-0003.json": SignalSet(**envelope, client_id="CL-0003"),
        "change_report/CL-0003.json": ChangeReport(
            **envelope, client_id="CL-0003", processing_mode="first_seen"
        ),
    }


def publish(root: Path, run: RunManifest, *, seed: bool = False) -> RunManifest:
    return publish_run(root, run, artifacts(run), seed=seed)


def test_run_identity_is_order_independent_and_changes_with_each_identity_input():
    left = compute_run_id(AS_OF, {"b": "2", "a": "1"}, {"d": "4", "c": "3"})
    assert left == compute_run_id(AS_OF, {"a": "1", "b": "2"}, {"c": "3", "d": "4"})
    variants = [
        compute_run_id(date(2026, 8, 25), {"b": "2", "a": "1"}, {"d": "4", "c": "3"}),
        compute_run_id(AS_OF, {"b": "changed", "a": "1"}, {"d": "4", "c": "3"}),
        compute_run_id(AS_OF, {"b": "2", "a": "1"}, {"d": "changed", "c": "3"}),
        compute_run_id(
            AS_OF,
            {"b": "2", "a": "1"},
            {"d": "4", "c": "3"},
            pipeline_version=f"{PIPELINE_VERSION}-next",
        ),
    ]
    assert all(value != left for value in variants)
    assert len(left) == 12


def test_repeated_publication_is_byte_identical_including_manifest_and_pointer(tmp_path):
    run = manifest()
    publish(tmp_path, run, seed=True)
    before = files(tmp_path)
    later = run.model_copy(
        update={"created_at": datetime(2026, 9, 6, tzinfo=UTC), "git_sha": "other"}
    )
    persisted = publish(tmp_path, later, seed=True)
    assert persisted == run
    assert files(tmp_path) == before


@pytest.mark.parametrize("bad_path", ["../escape.json", "/tmp/escape.json", "bundle.txt"])
def test_failed_publication_keeps_latest_and_existing_runs(tmp_path, bad_path):
    seed = manifest()
    publish(tmp_path, seed, seed=True)
    before = files(tmp_path)
    update = manifest(overlay=True)
    with pytest.raises(ValueError):
        publish_run(tmp_path, update, {bad_path: DataQualityReport(as_of=AS_OF)})
    assert files(tmp_path) == before
    assert not list((tmp_path / "runs").glob(".staging-*"))


def test_reset_repoints_latest_and_keeps_both_immutable_runs(tmp_path):
    seed = manifest()
    update = manifest(overlay=True)
    publish(tmp_path, seed, seed=True)
    publish(tmp_path, update)
    before = files(tmp_path / "runs")
    latest = read_latest(tmp_path)
    assert latest is not None
    assert latest["run_id"] == update.run_id
    assert latest["seed_run_id"] == seed.run_id
    reset = reset_latest(tmp_path)
    assert reset["run_id"] == seed.run_id
    assert reset["seed_run_id"] == seed.run_id
    assert files(tmp_path / "runs") == before


def test_identity_collision_never_changes_latest(tmp_path):
    seed = manifest()
    publish(tmp_path, seed, seed=True)
    before = files(tmp_path)
    collision = seed.model_copy(update={"source_hashes": {"clients.csv": "different"}})
    with pytest.raises(ValueError, match="identity|collision"):
        publish(tmp_path, collision)
    assert files(tmp_path) == before


def test_reset_without_seed_is_explicit_error(tmp_path):
    with pytest.raises(ValueError, match="seed"):
        reset_latest(tmp_path)


@pytest.mark.parametrize("defect", ["missing", "run_id", "as_of", "client", "model", "error"])
def test_invalid_artifact_sets_never_advance_latest(tmp_path, defect):
    seed = manifest()
    publish(tmp_path, seed, seed=True)
    before = files(tmp_path)
    update = manifest(overlay=True)
    payload = artifacts(update)
    key = "fact_bundle/CL-0003.json"
    if defect == "missing":
        payload.pop(key)
    elif defect == "run_id":
        payload[key] = payload[key].model_copy(update={"run_id": seed.run_id})
    elif defect == "as_of":
        payload[key] = payload[key].model_copy(update={"as_of": date(2025, 12, 31)})
    elif defect == "client":
        payload[key] = payload[key].model_copy(update={"client_id": "CL-0001"})
    elif defect == "model":
        payload[key] = payload["signal_set/CL-0003.json"]
    else:
        payload["data_quality_report.json"] = DataQualityReport(
            as_of=AS_OF,
            run_id=update.run_id,
            findings=[DataQualityFinding(code="BROKEN_KEY", severity="error", message="broken")],
        )
    with pytest.raises(ValueError):
        publish_run(tmp_path, update, payload)
    assert files(tmp_path) == before


def test_warning_tier_findings_do_not_block_publication(tmp_path):
    run = manifest()
    payload = artifacts(run)
    payload["data_quality_report.json"] = DataQualityReport(
        as_of=AS_OF,
        run_id=run.run_id,
        findings=[
            DataQualityFinding(code="LAGGED_VALUATION", severity="warning", message="lagged")
        ],
    )
    assert publish_run(tmp_path, run, payload).run_id == run.run_id


def test_serialization_failure_leaves_no_partial_run_or_changed_pointer(tmp_path):
    seed = manifest()
    publish(tmp_path, seed, seed=True)
    before = files(tmp_path)
    run = manifest(overlay=True)
    payload = artifacts(run)
    # Pydantic's float fields permit NaN, but JSON publication must not emit it.
    bundle = payload["curated_client_bundle/CL-0003.json"]
    assert isinstance(bundle, CuratedClientBundle)
    bundle.profile.total_aum_usd = float("nan")
    with pytest.raises(ValueError):
        publish_run(tmp_path, run, payload)
    assert files(tmp_path) == before
    assert not list((tmp_path / "runs").glob(".staging-*"))
