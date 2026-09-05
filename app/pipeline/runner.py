"""Run the deterministic pipeline across the full client book."""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

from app.pipeline.bundles import build_curated_bundle
from app.pipeline.changes import compare_client
from app.pipeline.features import AnalyticsProvider, legacy_analytics
from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.overlay import apply_overlay
from app.pipeline.publish import (
    DEFAULT_CURATED_DIR,
    PIPELINE_VERSION,
    compute_run_id,
    point_latest,
    publish_run,
    read_latest,
)
from app.pipeline.schemas import ContractModel, RunManifest
from app.pipeline.sources import source_versions
from app.pipeline.stages.clean import NormalizationRule, clean_sources
from app.pipeline.stages.ingest import IngestedSources, ingest_sources
from app.pipeline.stages.validate import source_evidence, validate_sources

DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_AS_OF = date(2026, 8, 26)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def run_pipeline(
    *,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    as_of: date = DEFAULT_AS_OF,
    overlay: Path | None = None,
    curated_dir: Path = DEFAULT_CURATED_DIR,
    analytics: AnalyticsProvider = legacy_analytics,
    pipeline_version: str = PIPELINE_VERSION,
    seed: bool = False,
    activate: bool = True,
    normalize_fx: NormalizationRule | None = None,
    normalize_bond_nominal: NormalizationRule | None = None,
    look_through: NormalizationRule | None = None,
) -> RunManifest:
    """Validate, clean, compute, diff and atomically publish all twenty Clients.

    pipeline_version identifies the entire computation, including the analytics provider and
    normalization callbacks. Callers must change it when any of those implementations change.
    The default version describes the transitional legacy provider, not Phase A analytics.
    activate=False stages an immutable run without selecting it as the dashboard's latest run.
    """
    hashes, issues = source_versions(source_dir)
    sources = ingest_sources(source_dir, as_of=as_of)
    validate_sources(sources)
    if issues:
        raise ValueError("; ".join(issues))
    merged = apply_overlay(sources.tables, sources.notes, overlay)

    def check_inputs_unchanged() -> None:
        if source_versions(source_dir) != (hashes, []):
            raise ValueError("Source files changed during pipeline execution; retry")
        if overlay is not None:
            try:
                current = {
                    path.name: sha256(path.read_bytes()).hexdigest()
                    for path in overlay.iterdir()
                    if path.is_file()
                }
            except OSError as exc:
                raise ValueError("Overlay files changed during pipeline execution; retry") from exc
            if current != merged.overlay_hashes:
                raise ValueError("Overlay files changed during pipeline execution; retry")

    merged_sources = IngestedSources(merged.tables, merged.notes, as_of)
    quality = validate_sources(merged_sources)
    run_id = compute_run_id(as_of, hashes, merged.overlay_hashes, pipeline_version=pipeline_version)
    store = ArtifactStore(curated_dir)
    try:
        existing = store.load_manifest(run_id)
    except ArtifactNotFound:
        existing = None
    if existing is not None:
        check_inputs_unchanged()
        if activate:
            point_latest(curated_dir, run_id, seed=seed)
        return existing
    prior_pointer = read_latest(curated_dir)
    prior_id = prior_pointer["run_id"] if prior_pointer else None
    prior_manifest = store.load_manifest(prior_id) if prior_id else None
    prior_evidence = store.load_evidence_map(run_id=prior_id) if prior_id else None
    # Capture eligible source values before normalization hooks can transform inputs.
    raw = clean_sources(merged.tables, merged.notes, as_of=as_of)
    evidence = source_evidence(IngestedSources(raw.tables, raw.notes, as_of))
    cleaned = clean_sources(
        merged.tables,
        merged.notes,
        as_of=as_of,
        normalize_fx=normalize_fx,
        normalize_bond_nominal=normalize_bond_nominal,
        look_through=look_through,
    )
    # Filtering and upserts must not replace physical source locations with merged indexes.
    for identifier, entry in evidence.entries.items():
        provenance = merged.provenance[identifier]
        entry.row_index = provenance["row_index"]
        entry.source_file = provenance["source_file"]
        entry.source = f"data/{entry.source_file}"
    quality.findings = [
        finding
        for finding in quality.findings
        if not finding.evidence_ids or any(key in evidence.entries for key in finding.evidence_ids)
    ]
    for finding in quality.findings:
        finding.evidence_ids = [key for key in finding.evidence_ids if key in evidence.entries]
    evidence.run_id = quality.run_id = run_id
    features = analytics(cleaned, run_id)
    if set(features.facts) != set(cleaned.clients) or set(features.signals) != set(cleaned.clients):
        raise ValueError("Analytics must return artifacts for every Client")
    changed_files = sorted(
        name
        for name in hashes.keys() | merged.overlay_hashes.keys()
        if prior_manifest is None
        or hashes.get(name) != prior_manifest.source_hashes.get(name)
        or merged.overlay_hashes.get(name) != prior_manifest.overlay_hashes.get(name)
    )
    if prior_manifest:
        changed_files = sorted(
            set(changed_files)
            | (prior_manifest.overlay_hashes.keys() - merged.overlay_hashes.keys())
        )
    hashes_match = bool(
        prior_manifest
        and hashes == prior_manifest.source_hashes
        and merged.overlay_hashes == prior_manifest.overlay_hashes
        and as_of == prior_manifest.as_of
        and pipeline_version == prior_manifest.pipeline_version
    )
    artifacts: dict[str, ContractModel] = {
        "evidence_map.json": evidence,
        "data_quality_report.json": quality,
    }
    for client_id in sorted(cleaned.clients):
        facts, signals = features.facts[client_id], features.signals[client_id]
        for bundle in (facts, signals):
            if (bundle.client_id, bundle.as_of, bundle.run_id) != (client_id, as_of, run_id):
                raise ValueError(f"Analytics artifact envelope mismatch for {client_id}")
        for members in (facts.facts, signals.signals):
            if len({item.id for item in members}) != len(members):
                raise ValueError(f"Analytics duplicate member identifiers for {client_id}")
            if any((item.client_id, item.as_of) != (client_id, as_of) for item in members):
                raise ValueError(f"Analytics member identity or as_of mismatch for {client_id}")
        fact_ids = {fact.id for fact in facts.facts}
        if any(set(signal.fact_ids) - fact_ids for signal in signals.signals):
            raise ValueError(f"Analytics Signal references unknown Facts for {client_id}")
        unresolved = {key for fact in facts.facts for key in fact.evidence_ids} | {
            key for signal in signals.signals for key in signal.evidence_ids
        }
        if unresolved - evidence.entries.keys():
            raise ValueError(
                f"Unresolved analytics Evidence: {sorted(unresolved - evidence.entries.keys())}"
            )
        curated = build_curated_bundle(cleaned, client_id, facts, signals)
        prior_curated = None
        prior_facts = prior_signals = None
        if prior_id:
            try:
                prior_curated = store.load_curated_bundle(client_id, run_id=prior_id)
                prior_facts = store.load_fact_bundle(client_id, run_id=prior_id)
                prior_signals = store.load_signal_set(client_id, run_id=prior_id)
            except ArtifactNotFound:
                pass
        # Agent-visible source context can change the conversation without changing a Fact.
        # Exclude run metadata and derived identifier lists from this per-client comparison.
        context_sections = (
            "profile",
            "portfolios",
            "holdings",
            "mandate_rules",
            "liquidity",
            "credit",
            "cash_needs",
            "commitments",
            "rm_notes",
        )
        changed_context = [
            section
            for section in context_sections
            if prior_curated is None or getattr(curated, section) != getattr(prior_curated, section)
        ]
        # Transactions remain exact Evidence rather than a CuratedClientBundle section.
        # Compare content by stable id, not file hashes or physical row locations.
        transactions = {
            key: entry.record
            for key, entry in evidence.entries.items()
            if entry.kind == "transactions" and entry.record.get("client_id") == client_id
        }
        prior_transactions = {
            key: entry.record
            for key, entry in (prior_evidence.entries.items() if prior_evidence else [])
            if entry.kind == "transactions" and entry.record.get("client_id") == client_id
        }
        if transactions != prior_transactions:
            changed_context.append("transactions")
        report = compare_client(
            facts,
            signals,
            prior_facts,
            prior_signals,
            changed_source_files=changed_files,
            changed_context_sections=changed_context,
            hashes_match=hashes_match,
        )
        artifacts[f"curated_client_bundle/{client_id}.json"] = curated
        artifacts[f"fact_bundle/{client_id}.json"] = facts
        artifacts[f"signal_set/{client_id}.json"] = signals
        artifacts[f"change_report/{client_id}.json"] = report
    # Refuse a mixed snapshot when another process changed inputs during computation.
    check_inputs_unchanged()
    manifest = RunManifest(
        run_id=run_id,
        as_of=as_of,
        pipeline_version=pipeline_version,
        git_sha=_git_sha(),
        source_hashes=hashes,
        overlay_hashes=merged.overlay_hashes,
        overridden_keys=merged.overridden_keys,
        client_ids=sorted(cleaned.clients),
        finding_counts={"error": quality.error_count, "warning": quality.warning_count},
        context_issues=features.context_issues,
        created_at=datetime.now(UTC),
    )
    return publish_run(curated_dir, manifest, artifacts, seed=seed, activate=activate)
