"""Pure read projection from immutable artifacts and persisted agent outputs.

Connected calendar records have `type` or `kind` equal to `calendar` or `meeting`.
Those records are returned unchanged; this layer never invents meeting dates.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.pipeline.api_schemas import ClientView, DataTab, DemoViewModel
from app.pipeline.loaders import ArtifactStore
from app.pipeline.schemas import ChangeReport, Fact
from app.store import ReviewLedger


def _failed(report: dict[str, Any]) -> bool:
    if report.get("passed") is False or report.get("errors"):
        return True
    checks = report.get("checks", [])
    if isinstance(checks, dict):
        checks = list(checks.values())
    return any(
        check is False or (isinstance(check, dict) and check.get("passed") is False)
        for check in checks
    )


def _has_text(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(_has_text(item) for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return _has_text(value["text"])
        return any(
            _has_text(item)
            for key, item in value.items()
            if key not in {"citations", "evidence_ids", "id", "client_id", "run_id"}
        )
    return False


def _prepared(brief: Any) -> bool:
    if not isinstance(brief, dict) or not brief:
        return False
    sections = brief.get("sections", brief)
    return (
        isinstance(sections, dict)
        and bool(sections)
        and all(
            _has_text(section)
            for key, section in sections.items()
            if key not in {"client_id", "run_id", "brief_version", "title", "as_of"}
        )
        and any(
            key not in {"client_id", "run_id", "brief_version", "title", "as_of"}
            for key in sections
        )
    )


def _data_tab(facts: list[Fact]) -> DataTab:
    """Group existing Facts by kind; presentation never computes financial values."""
    groups: dict[str, list[Fact]] = {name: [] for name in DataTab.model_fields}
    for fact in facts:
        kind = fact.kind.lower()
        if any(token in kind for token in ("cash_need", "cashflow", "deadline", "tax")):
            group = "cash_need"
        elif any(token in kind for token in ("collateral", "credit", "facility", "ltv")):
            group = "collateral"
        elif any(token in kind for token in ("mandate", "breach")):
            group = "mandate"
        elif any(token in kind for token in ("liquidity", "liquid", "headroom")):
            group = "liquidity"
        elif any(token in kind for token in ("change", "drift", "snapshot", "movement")):
            group = "snapshot_changes"
        else:
            group = "allocation"
        groups[group].append(fact)
    return DataTab.model_validate(groups)


def _insights(items: list[dict[str, Any]], changes: ChangeReport) -> list[dict[str, Any]]:
    added = {change.signal_id for change in changes.signal_changes if change.change == "added"}
    changed = {change.signal_id for change in changes.signal_changes if change.change != "added"}
    changed.update(changes.affected_signal_ids)
    result = []
    for original in items[:3]:
        insight = dict(original)
        identifiers = set(insight.get("signal_ids", []))
        if isinstance(insight.get("signal_id"), str):
            identifiers.add(insight["signal_id"])
        if isinstance(insight.get("id"), str):
            identifiers.add(insight["id"])
        insight["change_status"] = (
            "New" if identifiers & added else "Changed" if identifiers & changed else "Unchanged"
        )
        result.append(insight)
    return result


def _references(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_id" and isinstance(item, str):
                result.add(item)
            elif key in {"evidence_ids", "citations"} and isinstance(item, list):
                for reference in item:
                    if isinstance(reference, str):
                        result.add(reference)
                    elif isinstance(reference, dict):
                        identifier = reference.get("evidence_id", reference.get("id"))
                        if isinstance(identifier, str):
                            result.add(identifier)
            result.update(_references(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_references(item))
    return result


def _stale(source_dir: Path, source_hashes: dict[str, str], overlay_hashes: dict[str, str]) -> bool:
    for base, expected in (
        (source_dir, source_hashes),
        (source_dir / "fixtures/update", overlay_hashes),
    ):
        for name, digest in expected.items():
            path = base / name
            if not path.resolve().is_relative_to(base.resolve()):
                return True
            try:
                current = sha256(path.read_bytes()).hexdigest()
            except OSError:
                return True
            if current != digest:
                return True
    return False


def build_view_model(
    store: ArtifactStore,
    ledger: ReviewLedger,
    source_dir: Path | str,
    updating: bool = False,
) -> DemoViewModel:
    """Read one pinned run and its current briefs without running agents or writing state."""
    manifest = store.load_manifest()
    clients: dict[str, ClientView] = {}
    calendar: list[dict[str, Any]] = []
    calendar_seen: set[str] = set()
    references: dict[str, set[str]] = {}
    needs_confirmation = (
        bool(manifest.context_issues)
        or store.load_data_quality_report(run_id=manifest.run_id).has_errors
    )
    for client_id in manifest.client_ids:
        bundle = store.load_curated_bundle(client_id, run_id=manifest.run_id)
        facts = store.load_fact_bundle(client_id, run_id=manifest.run_id)
        signals = store.load_signal_set(client_id, run_id=manifest.run_id)
        changes = store.load_change_report(client_id, run_id=manifest.run_id)
        quality = store.load_data_quality_report(run_id=manifest.run_id, client_id=client_id)
        persisted = ledger.get_brief(client_id, manifest.run_id)
        body = persisted.body if persisted else {}
        verification = persisted.verification_report if persisted else {}
        context_issues = list(manifest.context_issues) + body.get("context_issues", [])
        failed = _failed(verification)
        client_unconfirmed = failed or quality.has_errors or bool(context_issues)
        needs_confirmation = needs_confirmation or client_unconfirmed
        brief = body.get("meeting_brief")
        status = (
            "Not prepared"
            if not _prepared(brief)
            else (
                "Needs review"
                if client_unconfirmed or verification.get("passed") is not True
                else "Ready"
            )
        )
        connected = body.get("connected_context", [])
        for item in connected:
            if item.get("type") in {"calendar", "meeting"} or item.get("kind") in {
                "calendar",
                "meeting",
            }:
                key = json.dumps(item, sort_keys=True)
                if key not in calendar_seen:
                    calendar.append(item)
                    calendar_seen.add(key)
        clients[client_id] = ClientView(
            header=bundle.profile,
            insights=_insights(body.get("insights", []), changes),
            meeting_brief=brief,
            brief_version=persisted.brief_version if persisted else None,
            memory_card=body.get("memory_card"),
            data_tab=_data_tab(facts.facts),
            memory_tab=[*connected, *(note.model_dump(mode="json") for note in bundle.rm_notes)],
            change_report=changes,
            quality_findings=quality.findings,
            brief_status=status,
            verification=verification,
            context_issues=context_issues,
        )
        references.update({fact.id: set(fact.evidence_ids) for fact in facts.facts})
        for signal in signals.signals:
            references[signal.id] = set(signal.evidence_ids)
            for fact_id in signal.fact_ids:
                references[signal.id].update(references.get(fact_id, set()))
    health = (
        "Needs confirmation"
        if needs_confirmation
        else (
            "Stale"
            if _stale(Path(source_dir), manifest.source_hashes, manifest.overlay_hashes)
            else ("Updating" if updating else "Current")
        )
    )
    result = DemoViewModel(
        as_of=manifest.as_of,
        run_id=manifest.run_id,
        refreshed_at=datetime.now(UTC),
        data_health=health,
        clients=clients,
        calendar=calendar,
        reviews=ledger.list(manifest.run_id),
    )
    requested = _references(result.model_dump(mode="json"))
    evidence_ids = set()
    for identifier in requested:
        evidence_ids.update(references.get(identifier, {identifier}))
    result.evidence = store.load_evidence(sorted(evidence_ids), run_id=manifest.run_id)
    return result
