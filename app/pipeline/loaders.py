"""Typed, read-only artifact registry consumed by the agent layer."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

from app.pipeline.publish import DEFAULT_CURATED_DIR, read_latest, validate_run_id
from app.pipeline.schemas import (
    Artifact,
    ChangeReport,
    CuratedClientBundle,
    DataQualityReport,
    Evidence,
    EvidenceMap,
    FactBundle,
    RunManifest,
    SignalSet,
)


class ArtifactNotFound(FileNotFoundError):
    """The requested published run, client artifact, or evidence ID is absent."""


def _client_id(client_id: str) -> str:
    if not re.fullmatch(r"CL-\d{4}", client_id):
        raise ValueError("Invalid client_id")
    return client_id


class ArtifactStore:
    """Read immutable run artifacts from a specific curated output directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def _run_id(self, run_id: str | None) -> str:
        if run_id is not None:
            return validate_run_id(run_id)
        pointer = self.root / "latest.json"
        self._contained(pointer)
        latest = read_latest(self.root)
        if latest is None:
            raise ArtifactNotFound(f"No published latest run in {self.root}")
        return validate_run_id(latest["run_id"])

    def _contained(self, path: Path) -> None:
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Artifact path escapes the curated directory")

    def _read[T: Artifact](self, run_id: str, name: str, model: type[T]) -> T:
        path = self.root / "runs" / run_id / name
        self._contained(path)
        try:
            artifact = model.model_validate_json(path.read_bytes())
        except FileNotFoundError as exc:
            raise ArtifactNotFound(f"Missing artifact {name} in run {run_id}") from exc
        if artifact.run_id != run_id:
            raise ValueError(f"Artifact {name} belongs to a different run")
        return artifact

    def load_manifest(self, run_id: str | None = None) -> RunManifest:
        return self._read(self._run_id(run_id), "manifest.json", RunManifest)

    def _client_artifact[T: CuratedClientBundle | FactBundle | SignalSet | ChangeReport](
        self,
        client_id: str,
        run_id: str | None,
        directory: str,
        model: type[T],
    ) -> T:
        _client_id(client_id)
        manifest = self.load_manifest(run_id)
        if client_id not in manifest.client_ids:
            raise ArtifactNotFound(f"Client {client_id} is absent from run {manifest.run_id}")
        artifact = self._read(manifest.run_id, f"{directory}/{client_id}.json", model)
        if artifact.client_id != client_id:
            raise ValueError(f"Artifact belongs to a different client than {client_id}")
        return artifact

    def load_curated_bundle(
        self,
        client_id: str,
        *,
        run_id: str | None = None,
    ) -> CuratedClientBundle:
        return self._client_artifact(
            client_id,
            run_id,
            "curated_client_bundle",
            CuratedClientBundle,
        )

    def load_fact_bundle(self, client_id: str, *, run_id: str | None = None) -> FactBundle:
        return self._client_artifact(client_id, run_id, "fact_bundle", FactBundle)

    def load_signal_set(self, client_id: str, *, run_id: str | None = None) -> SignalSet:
        return self._client_artifact(client_id, run_id, "signal_set", SignalSet)

    def load_change_report(self, client_id: str, *, run_id: str | None = None) -> ChangeReport:
        return self._client_artifact(client_id, run_id, "change_report", ChangeReport)

    def load_evidence(
        self,
        evidence_ids: Iterable[str],
        *,
        run_id: str | None = None,
    ) -> dict[str, Evidence]:
        manifest = self.load_manifest(run_id)
        evidence = self._read(manifest.run_id, "evidence_map.json", EvidenceMap)
        requested = list(dict.fromkeys(evidence_ids))
        missing = [identifier for identifier in requested if identifier not in evidence.entries]
        if missing:
            raise ArtifactNotFound(
                f"Missing evidence in run {manifest.run_id}: {', '.join(missing)}"
            )
        return {identifier: evidence.entries[identifier] for identifier in requested}

    def load_data_quality_report(
        self,
        *,
        run_id: str | None = None,
        client_id: str | None = None,
    ) -> DataQualityReport:
        if client_id is not None:
            _client_id(client_id)
        manifest = self.load_manifest(run_id)
        if client_id is not None and client_id not in manifest.client_ids:
            raise ArtifactNotFound(f"Client {client_id} is absent from run {manifest.run_id}")
        report = self._read(manifest.run_id, "data_quality_report.json", DataQualityReport)
        if client_id is None:
            return report
        return report.model_copy(
            update={
                "findings": [
                    item for item in report.findings if item.client_id in (None, client_id)
                ],
            }
        )


def _store() -> ArtifactStore:
    return ArtifactStore(os.environ.get("PIPELINE_CURATED_DIR") or DEFAULT_CURATED_DIR)


def load_manifest(run_id: str | None = None) -> RunManifest:
    return _store().load_manifest(run_id)


def load_curated_bundle(client_id: str, *, run_id: str | None = None) -> CuratedClientBundle:
    return _store().load_curated_bundle(client_id, run_id=run_id)


def load_fact_bundle(client_id: str, *, run_id: str | None = None) -> FactBundle:
    return _store().load_fact_bundle(client_id, run_id=run_id)


def load_signal_set(client_id: str, *, run_id: str | None = None) -> SignalSet:
    return _store().load_signal_set(client_id, run_id=run_id)


def load_change_report(client_id: str, *, run_id: str | None = None) -> ChangeReport:
    return _store().load_change_report(client_id, run_id=run_id)


def load_evidence(
    evidence_ids: Iterable[str],
    *,
    run_id: str | None = None,
) -> dict[str, Evidence]:
    return _store().load_evidence(evidence_ids, run_id=run_id)


def load_data_quality_report(
    *,
    run_id: str | None = None,
    client_id: str | None = None,
) -> DataQualityReport:
    return _store().load_data_quality_report(run_id=run_id, client_id=client_id)
