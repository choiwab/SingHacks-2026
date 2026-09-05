"""Synchronous seed/update/reset orchestration around persisted run-scoped artifacts."""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from pathlib import Path
from threading import RLock
from typing import Any

from app.pipeline.features import AnalyticsProvider, legacy_analytics
from app.pipeline.graph_adapter import AgentHooks, execute_client, verify_brief
from app.pipeline.loaders import ArtifactStore
from app.pipeline.publish import point_latest, read_latest
from app.pipeline.runner import DEFAULT_AS_OF, DEFAULT_SOURCE_DIR, run_pipeline
from app.pipeline.schemas import ReviewRequest, RunManifest
from app.pipeline.verification_state import verification_passed
from app.store import ReviewLedger


class PipelineRuntime:
    """Serialize mutations across threads/processes; reads consume committed state only."""

    def __init__(
        self,
        store: ArtifactStore,
        ledger: ReviewLedger,
        *,
        source_dir: Path = DEFAULT_SOURCE_DIR,
        as_of: date = DEFAULT_AS_OF,
        overlay_dir: Path | None = None,
        analytics: AnalyticsProvider = legacy_analytics,
        agents: AgentHooks | None = None,
    ):
        self.store, self.ledger = store, ledger
        self.source_dir, self.as_of = source_dir, as_of
        self.overlay_dir = overlay_dir or source_dir / "fixtures/update"
        self.analytics, self.agents = analytics, agents
        self.lock = RLock()

    @contextmanager
    def _mutation(self) -> Iterator[None]:
        """Coordinate runtime instances sharing a curated store (Unix deployment)."""
        with self.lock:
            self.store.root.mkdir(parents=True, exist_ok=True)
            with (self.store.root / ".runtime.lock").open("a") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def seed(self) -> RunManifest:
        with self._mutation():
            return self._run(seed=True)

    def update(self) -> RunManifest:
        with self._mutation():
            if not read_latest(self.store.root):
                self._run(seed=True)
            return self._run(seed=False)

    def reset(self) -> RunManifest:
        with self._mutation():
            pointer = read_latest(self.store.root)
            if pointer is None or not pointer.get("seed_run_id"):
                raise ValueError("No seed run has been published")
            manifest = self.store.load_manifest(pointer["seed_run_id"])
            self._prepare(manifest, seed=True)
            point_latest(self.store.root, manifest.run_id)
            return manifest

    def prepare_current(self) -> RunManifest | None:
        """Hydrate missing ledger outputs from the current run without recomputing it."""
        with self._mutation():
            pointer = read_latest(self.store.root)
            if pointer is None:
                return None
            manifest = self.store.load_manifest(pointer["run_id"])
            self._prepare(manifest, seed=pointer.get("seed_run_id") == manifest.run_id)
            return manifest

    def _run(self, *, seed: bool) -> RunManifest:
        manifest = run_pipeline(
            source_dir=self.source_dir,
            as_of=self.as_of,
            overlay=None if seed else self.overlay_dir,
            curated_dir=self.store.root,
            analytics=self.analytics,
            seed=seed,
            activate=False,
        )
        self._prepare(manifest, seed=seed)
        point_latest(self.store.root, manifest.run_id, seed=seed)
        return manifest

    def _prepare(self, manifest: RunManifest, *, seed: bool) -> None:
        if self.ledger.get_run(manifest.run_id) is None:
            self.ledger.add_run(
                run_id=manifest.run_id,
                pipeline_version=manifest.pipeline_version,
                as_of=manifest.as_of,
                source_hashes=manifest.source_hashes,
                overlay_hashes=manifest.overlay_hashes,
                is_seed=seed,
            )
        for client_id in manifest.client_ids:
            if self.ledger.get_brief(client_id, manifest.run_id) is not None:
                continue
            report = self.store.load_change_report(client_id, run_id=manifest.run_id)
            previous_brief = (
                self.ledger.get_brief(client_id, report.prior_run_id)
                if report.prior_run_id
                else None
            )
            if report.processing_mode == "no_material_change" and previous_brief:
                body = deepcopy(previous_brief.body)
                verification = verify_brief(
                    self.store,
                    client_id,
                    manifest.run_id,
                    body,
                    verifier=self.agents.verifier if self.agents else None,
                    brief_version=1,
                )
            else:
                output = execute_client(self.store, client_id, manifest.run_id, agents=self.agents)
                body = {key: value for key, value in output.items() if key != "verification_report"}
                verification = {**output["verification_report"], "brief_version": 1}
            self.ledger.store_brief(
                client_id=client_id,
                run_id=manifest.run_id,
                body=body,
                verification_report=verification,
                brief_version=1,
            )

    def review(self, request: ReviewRequest) -> dict[str, Any]:
        with self._mutation():
            latest = self.store.load_manifest()
            if request.run_id != latest.run_id:
                raise ValueError("Review run is no longer current")
            if request.client_id not in latest.client_ids:
                raise KeyError("Client not found")
            current = self.ledger.get_brief(request.client_id, latest.run_id)
            if current is None or current.brief_version != request.brief_version:
                raise ValueError("Brief version is no longer current")
            version = current.brief_version
            report = current.verification_report
            if request.action == "Edit":
                body = deepcopy(current.body)
                if not request.text.strip():
                    raise ValueError("Edit requires replacement text")
                if self.agents and self.agents.edit:
                    if not request.section:
                        raise KeyError("Meeting Brief claim not found")
                    body = self.agents.edit(body, request.section, request.text)
                elif body.get("pack") is not None:
                    raise ValueError("Meeting pack editing requires the configured agent adapter")
                else:
                    brief = body.get("meeting_brief") or {}
                    sections = brief.get("sections") or {}
                    if not request.section or request.section not in sections:
                        raise KeyError("Meeting Brief section not found")
                    original = sections[request.section]
                    if isinstance(original, dict):
                        sections[request.section] = {**original, "text": request.text}
                    else:
                        sections[request.section] = {"text": request.text}
                version += 1
                report = verify_brief(
                    self.store,
                    request.client_id,
                    latest.run_id,
                    body,
                    verifier=self.agents.verifier if self.agents else None,
                )
                report["brief_version"] = version
                body["trace"] = [
                    *body.get("trace", []),
                    {
                        "node": "review",
                        "action": "Edit",
                        "brief_version": version,
                        "verification_passed": verification_passed(report),
                    },
                ]
                current = self.ledger.store_brief(
                    client_id=request.client_id,
                    run_id=latest.run_id,
                    body=body,
                    verification_report=report,
                    origin="rm_edited",
                    brief_version=version,
                )
            elif request.action == "Approve" and not verification_passed(report):
                raise ValueError("Meeting Brief has not passed verification")
            recorded = request.model_copy(update={"brief_version": version})
            review = self.ledger.append(
                recorded,
                rm="Priscilla Ong",
                verification_report_id=f"{latest.run_id}:{request.client_id}:{version}",
            )
            return {"review": review, "brief_version": version, "verification_report": report}
