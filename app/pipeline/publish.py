"""Content-addressed, immutable artifact directories and atomic latest pointers."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.pipeline.schemas import (
    Artifact,
    ChangeReport,
    ContractModel,
    CuratedClientBundle,
    DataQualityReport,
    EvidenceMap,
    FactBundle,
    RunManifest,
    SignalSet,
)

PIPELINE_VERSION = "1"
DEFAULT_CURATED_DIR = Path(__file__).resolve().parents[2] / "data/generated/curated"


def canonical_json(value: Any) -> bytes:
    if isinstance(value, ContractModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode()


def compute_run_id(
    as_of: date,
    source_hashes: dict[str, str],
    overlay_hashes: dict[str, str],
    *,
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    payload = {
        "pipeline_version": pipeline_version,
        "as_of": as_of.isoformat(),
        "source_hashes": source_hashes,
        "overlay_hashes": overlay_hashes,
    }
    return sha256(canonical_json(payload)).hexdigest()[:12]


def validate_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Invalid run_id")
    return run_id


def read_latest(root: Path = DEFAULT_CURATED_DIR) -> dict[str, Any] | None:
    path = root / "latest.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    validate_run_id(value["run_id"])
    if value.get("seed_run_id") is not None:
        validate_run_id(value["seed_run_id"])
    return value


def point_latest(root: Path, run_id: str, *, seed: bool = False) -> dict[str, Any]:
    validate_run_id(run_id)
    if not (root / "runs" / run_id / "manifest.json").is_file():
        raise FileNotFoundError(f"Run {run_id} is not published")
    previous = read_latest(root)
    seed_id = run_id if seed else (previous or {}).get("seed_run_id")
    if previous and previous["run_id"] == run_id and previous.get("seed_run_id") == seed_id:
        return previous
    pointer = {
        "run_id": run_id,
        "seed_run_id": seed_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    fd, temporary = tempfile.mkstemp(prefix=".latest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_json(pointer))
        os.replace(temporary, root / "latest.json")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return pointer


def publish_run(
    root: Path,
    manifest: RunManifest,
    artifacts: dict[str, ContractModel],
    *,
    seed: bool = False,
    activate: bool = True,
) -> RunManifest:
    """Stage all JSON first, atomically expose a run, then update latest.json."""
    run_id = validate_run_id(manifest.run_id)
    expected_id = compute_run_id(
        manifest.as_of,
        manifest.source_hashes,
        manifest.overlay_hashes,
        pipeline_version=manifest.pipeline_version,
    )
    if run_id != expected_id:
        raise ValueError("Run identity does not match its input fingerprint")
    required: dict[str, type[Artifact]] = {
        "evidence_map.json": EvidenceMap,
        "data_quality_report.json": DataQualityReport,
    }
    per_client = {
        "curated_client_bundle": CuratedClientBundle,
        "fact_bundle": FactBundle,
        "signal_set": SignalSet,
        "change_report": ChangeReport,
    }
    if len(set(manifest.client_ids)) != len(manifest.client_ids):
        raise ValueError("Manifest contains duplicate client ids")
    for client_id in manifest.client_ids:
        for directory, model in per_client.items():
            required[f"{directory}/{client_id}.json"] = model
    if set(artifacts) != set(required):
        raise ValueError("Artifact paths must match the complete manifest inventory")
    for name, model in required.items():
        artifact = artifacts[name]
        if not isinstance(artifact, model):
            raise ValueError(f"Unexpected artifact model for {name}")
        if artifact.run_id != run_id or artifact.as_of != manifest.as_of:
            raise ValueError(f"Artifact envelope does not match manifest: {name}")
        client_id = getattr(artifact, "client_id", None)
        if client_id is not None and name.rsplit("/", 1)[-1] != f"{client_id}.json":
            raise ValueError(f"Artifact client does not match its path: {name}")
    quality = artifacts["data_quality_report.json"]
    if isinstance(quality, DataQualityReport) and quality.has_errors:
        raise ValueError("Data quality errors block publication")
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    destination = runs / run_id
    if destination.exists():
        existing = RunManifest.model_validate_json((destination / "manifest.json").read_bytes())
        if (
            existing.source_hashes,
            existing.overlay_hashes,
            existing.as_of,
            existing.pipeline_version,
        ) != (
            manifest.source_hashes,
            manifest.overlay_hashes,
            manifest.as_of,
            manifest.pipeline_version,
        ):
            raise ValueError("Run identity collision")
        if activate:
            point_latest(root, run_id, seed=seed)
        return existing
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=runs))
    try:
        for name, artifact in sorted(artifacts.items()):
            target = staging / name
            if target.suffix != ".json" or not target.resolve().is_relative_to(staging.resolve()):
                raise ValueError("Invalid artifact path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(canonical_json(artifact))
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        os.rename(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if activate:
        point_latest(root, run_id, seed=seed)
    return manifest


def reset_latest(root: Path = DEFAULT_CURATED_DIR) -> dict[str, Any]:
    latest = read_latest(root)
    if not latest or not latest.get("seed_run_id"):
        raise ValueError("No seed run has been published")
    return point_latest(root, latest["seed_run_id"])
