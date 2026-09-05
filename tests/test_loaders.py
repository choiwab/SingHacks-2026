"""Loader contracts against small published JSON directories."""

import json

import pytest
from pydantic import ValidationError

from app.pipeline import loaders
from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.schemas import (
    ChangeReport,
    CuratedClientBundle,
    DataQualityReport,
    Evidence,
    FactBundle,
    RunManifest,
    SignalSet,
)

SEED = "012345abcdef"
UPDATE = "fedcba543210"
CLIENT = "CL-0003"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def publish_fixture(root, run_id=SEED):
    run = root / "runs" / run_id
    envelope = {"as_of": "2026-08-26", "run_id": run_id}
    write(
        run / "manifest.json",
        {
            **envelope,
            "pipeline_version": "1",
            "git_sha": "abc",
            "source_hashes": {},
            "client_ids": [CLIENT, "CL-0002"],
            "created_at": "2026-09-05T00:00:00Z",
        },
    )
    profile = {
        "client_id": CLIENT,
        "client_name": "Example",
        "age": 60,
        "gender": "F",
        "nationality": "DE",
        "country_of_residence": "DE",
        "tax_domicile": "DE",
        "booking_centre": "SG",
        "rm_id": "RM1",
        "rm_name": "RM",
        "rm_desk": "SG",
        "base_currency": "EUR",
        "wealth_band": "UHNW",
        "life_stage": "Retired",
        "source_of_wealth": "Business",
        "risk_profile": "Conservative",
        "risk_tolerance_score": 2,
        "investment_horizon_years": 5,
        "liquidity_needs": "Tax",
        "objectives": "Preserve capital",
        "client_since": "2000-01-01",
        "kyc_review_due": "2027-01-01",
        "pep_status": "No",
        "reporting_language": "English",
    }
    write(
        run / "curated_client_bundle" / f"{CLIENT}.json",
        {
            **envelope,
            "client_id": CLIENT,
            "profile": profile,
        },
    )
    for directory in ("fact_bundle", "signal_set", "change_report"):
        value = {**envelope, "client_id": CLIENT}
        if directory == "change_report":
            value["processing_mode"] = "first_seen"
        write(run / directory / f"{CLIENT}.json", value)
    write(
        run / "evidence_map.json",
        {
            **envelope,
            "entries": {
                "rm_notes:N-005": {
                    "id": "rm_notes:N-005",
                    "kind": "rm_notes",
                    "title": "Note",
                    "source": "rm_notes.json",
                    "record": {"note": run_id},
                },
            },
        },
    )
    write(
        run / "data_quality_report.json",
        {
            **envelope,
            "findings": [
                {"code": "GLOBAL", "severity": "warning", "message": "Global finding"},
                {"code": "OWN", "severity": "warning", "message": "Own", "client_id": CLIENT},
                {
                    "code": "OTHER",
                    "severity": "warning",
                    "message": "Other",
                    "client_id": "CL-0002",
                },
            ],
        },
    )
    write(root / "latest.json", {"run_id": run_id, "seed_run_id": SEED})
    return run


def test_all_loaders_return_models_and_top_level_functions_honor_environment(tmp_path, monkeypatch):
    publish_fixture(tmp_path)
    monkeypatch.setenv("PIPELINE_CURATED_DIR", str(tmp_path))
    assert isinstance(loaders.load_manifest(), RunManifest)
    assert isinstance(loaders.load_curated_bundle(CLIENT), CuratedClientBundle)
    assert isinstance(loaders.load_fact_bundle(CLIENT), FactBundle)
    assert isinstance(loaders.load_signal_set(CLIENT), SignalSet)
    assert isinstance(loaders.load_change_report(CLIENT), ChangeReport)
    assert isinstance(loaders.load_data_quality_report(), DataQualityReport)
    evidence = loaders.load_evidence(["rm_notes:N-005", "rm_notes:N-005"])
    assert list(evidence) == ["rm_notes:N-005"]
    assert isinstance(evidence["rm_notes:N-005"], Evidence)
    assert loaders.load_evidence([]) == {}


def test_explicit_run_stays_pinned_while_latest_changes(tmp_path):
    publish_fixture(tmp_path)
    store = ArtifactStore(tmp_path)
    publish_fixture(tmp_path, UPDATE)
    assert store.load_manifest().run_id == UPDATE
    assert store.load_manifest(SEED).run_id == SEED
    assert store.load_evidence(["rm_notes:N-005"], run_id=SEED)["rm_notes:N-005"].record == {
        "note": SEED,
    }
    assert store.load_fact_bundle(CLIENT, run_id=SEED).run_id == SEED


def test_missing_latest_run_client_artifact_and_evidence_raise(tmp_path):
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactNotFound):
        store.load_manifest()
    with pytest.raises(ArtifactNotFound):
        store.load_manifest(UPDATE)
    run = publish_fixture(tmp_path)
    with pytest.raises(ArtifactNotFound):
        store.load_fact_bundle("CL-9999")
    with pytest.raises(ArtifactNotFound):
        store.load_fact_bundle("CL-0002")
    with pytest.raises(ArtifactNotFound, match="missing"):
        store.load_evidence(["rm_notes:N-005", "missing"])
    (run / "evidence_map.json").unlink()
    with pytest.raises(ArtifactNotFound):
        store.load_evidence([])


def test_client_quality_includes_global_findings_without_other_clients(tmp_path):
    publish_fixture(tmp_path)
    store = ArtifactStore(tmp_path)
    assert len(store.load_data_quality_report().findings) == 3
    report = store.load_data_quality_report(client_id=CLIENT)
    assert [finding.code for finding in report.findings] == ["GLOBAL", "OWN"]
    with pytest.raises(ArtifactNotFound):
        store.load_data_quality_report(client_id="CL-9999")


@pytest.mark.parametrize("identifier", ["../outside", "/tmp", "ABCDEF123456", "123"])
def test_invalid_run_ids_rejected(tmp_path, identifier):
    with pytest.raises(ValueError, match="Invalid run_id"):
        ArtifactStore(tmp_path).load_manifest(identifier)


@pytest.mark.parametrize("identifier", ["../outside", "CL-1", "/tmp"])
def test_invalid_client_ids_rejected(tmp_path, identifier):
    with pytest.raises(ValueError, match="Invalid client_id"):
        ArtifactStore(tmp_path).load_fact_bundle(identifier)


def test_symlink_escape_rejected(tmp_path):
    root = tmp_path / "root"
    publish_fixture(root)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    target = root / "runs" / SEED / "fact_bundle" / f"{CLIENT}.json"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        ArtifactStore(root).load_fact_bundle(CLIENT)


def test_corrupt_or_misidentified_artifacts_fail_validation(tmp_path):
    run = publish_fixture(tmp_path)
    store = ArtifactStore(tmp_path)
    target = run / "fact_bundle" / f"{CLIENT}.json"
    write(target, {"run_id": SEED})
    with pytest.raises(ValidationError):
        store.load_fact_bundle(CLIENT)
    write(target, {"as_of": "2026-08-26", "run_id": UPDATE, "client_id": CLIENT})
    with pytest.raises(ValueError, match="different run"):
        store.load_fact_bundle(CLIENT)
    write(target, {"as_of": "2026-08-26", "run_id": SEED, "client_id": "CL-0002"})
    with pytest.raises(ValueError, match="different client"):
        store.load_fact_bundle(CLIENT)
