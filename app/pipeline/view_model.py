"""Pure read projection from immutable artifacts and persisted agent outputs.

Connected calendar records have `type` or `kind` equal to `calendar` or `meeting`.
Those records are returned unchanged; this layer never invents meeting dates.
"""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.pipeline.api_schemas import ClientHeader, ClientRanking, ClientView, DataTab, DemoViewModel
from app.pipeline.loaders import ArtifactStore
from app.pipeline.member2_bridge import derive_signals
from app.pipeline.schemas import ChangeReport, Fact
from app.pipeline.verification_state import verification_passed
from app.store import ReviewLedger

LEGACY_SIGNAL_NOTICE = "Phase A Signal definitions are not connected; legacy Facts only."


def _blocking_context(issues: list[str]) -> bool:
    # M2 derives verified signals from the pinned legacy Facts; retain the notice for audit.
    return any(issue != LEGACY_SIGNAL_NOTICE for issue in issues)


def _ranking(
    client: ClientView, facts: list[Fact], signals: list[Any], calendar: list[dict[str, Any]]
) -> ClientRanking:
    """Priority is the maximum existing signal component (0-100), with ties by client ID.

    Legacy runs rebuild the same scorer's components from pinned Facts. Urgency uses
    the scorer's existing 65/45 thresholds. Meetings display Singapore local time.
    """
    derived = derive_signals(client.header.client_id, facts) if not signals else []
    drivers = [(signal.priority_score, signal.id) for signal in signals] or [
        (signal.score, signal.id) for signal in derived
    ]
    score, driver = max(drivers, default=(0.0, ""))
    reasons = {
        "suitability": "Mandate alignment and concentration lead the review.",
        "funding": "The next funding deadline leads the review.",
        "portfolio-change": "Portfolio changes and their consequences lead the review.",
    }
    meetings = sorted(
        datetime.fromisoformat(item["scheduled_at"])
        for item in calendar
        if item.get("client_id") == client.header.client_id and item.get("scheduled_at")
    )
    return ClientRanking(
        client_id=client.header.client_id,
        name=client.header.client_name,
        score=float(score),
        urgency="now" if score >= 65 else "soon" if score >= 45 else "watch",
        meeting=meetings[0].astimezone(ZoneInfo("Asia/Singapore")).strftime("%a %H:%M")
        if meetings
        else None,
        reason=reasons.get(
            driver.rsplit(":", 1)[-1],
            f"Signal {driver} leads the review."
            if driver
            else "No scored signal is available for review.",
        ),
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
            if key in {"evidence_id", "record_id"} and isinstance(item, str):
                result.add(item)
            elif key in {"evidence_ids", "record_ids", "citations"} and isinstance(item, list):
                for reference in item:
                    if isinstance(reference, str):
                        result.add(reference)
                    elif isinstance(reference, dict):
                        identifier = reference.get(
                            "evidence_id", reference.get("record_id", reference.get("id"))
                        )
                        if isinstance(identifier, str):
                            result.add(identifier)
            result.update(_references(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_references(item))
    return result


def _connected_chunks(
    body: dict[str, Any], client_id: str, records: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Resolve exact persisted index entries against their own cached parent record."""
    snapshot = body.get("memory_index")
    if not isinstance(snapshot, dict) or snapshot.get("client_id") != client_id:
        return {}
    chunks, versions = snapshot.get("chunks"), snapshot.get("record_versions")
    if not isinstance(chunks, dict) or not isinstance(versions, dict):
        return {}
    parents = {record.get("id"): record for record in records}
    resolved = {}
    for identifier, chunk in chunks.items():
        if not isinstance(chunk, dict) or chunk.get("id") != identifier:
            continue
        record_id = chunk.get("record_id")
        if not isinstance(record_id, str):
            continue
        parent, version = parents.get(record_id), versions.get(record_id)
        if parent is None or parent.get("client_id") != client_id or not isinstance(version, str):
            continue
        start, end, text = chunk.get("start"), chunk.get("end"), parent.get("text")
        if (
            type(start) is not int
            or type(end) is not int
            or not isinstance(text, str)
            or not 0 <= start < end <= len(text)
            or text[start:end] != chunk.get("text")
        ):
            continue
        resolved[identifier] = {"chunk": chunk, "record": parent, "record_version": version}
    return resolved


def _stale(source_dir: Path, source_hashes: dict[str, str], overlay_hashes: dict[str, str]) -> bool:
    if overlay_hashes:
        overlay = source_dir / "fixtures/update"
        current_files = (
            {
                path.name
                for path in overlay.iterdir()
                if path.is_file() and path.suffix in {".csv", ".json"}
            }
            if overlay.is_dir()
            else set()
        )
        if current_files != set(overlay_hashes):
            return True
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
    ranking: list[ClientRanking] = []
    references: dict[str, set[str]] = {}
    connected_records: dict[str, dict[str, Any]] = {}
    reviews = ledger.list(manifest.run_id)
    needs_confirmation = (
        _blocking_context(manifest.context_issues)
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
        verified = verification_passed(verification)
        failed = persisted is not None and not verified
        client_unconfirmed = failed or quality.has_errors or _blocking_context(context_issues)
        needs_confirmation = needs_confirmation or client_unconfirmed
        brief = body.get("meeting_brief")
        applicable_reviews = [
            review
            for review in reviews
            if review.client_id == client_id
            and persisted is not None
            and review.brief_version == persisted.brief_version
        ]
        approved = bool(applicable_reviews) and applicable_reviews[-1].action == "Approve"
        status = (
            "Not prepared"
            if not _prepared(brief)
            else ("Needs review" if client_unconfirmed or not verified or not approved else "Ready")
        )
        connected = body.get("connected_context", [])
        # PR30 persists a ConnectedContext envelope; older runs stored its records directly.
        if isinstance(connected, dict):
            connected = connected.get("records", [])
        for item in connected:
            identifier = item.get("id", item.get("record_id"))
            if isinstance(identifier, str):
                previous = connected_records.get(identifier)
                if previous is not None and previous != item:
                    raise ValueError(f"Conflicting connected record: {identifier}")
                connected_records[identifier] = item
            if (
                item.get("type") in {"calendar", "meeting"}
                or item.get("source") == "calendar"
                or item.get("kind")
                in {
                    "calendar",
                    "meeting",
                }
            ):
                key = json.dumps(item, sort_keys=True)
                if key not in calendar_seen:
                    calendar.append(item)
                    calendar_seen.add(key)
        connected_records.update(_connected_chunks(body, client_id, connected))
        clients[client_id] = ClientView(
            header=ClientHeader.model_validate(
                {
                    key: value
                    for key, value in bundle.profile.model_dump().items()
                    if key in ClientHeader.model_fields
                }
            ),
            insights=_insights(body.get("insights", []), changes) if verified else [],
            meeting_brief=brief if verified else None,
            brief_version=persisted.brief_version if persisted else None,
            memory_card=body.get("memory_card") if verified else None,
            data_tab=_data_tab(facts.facts),
            memory_tab=[*connected, *(note.model_dump(mode="json") for note in bundle.rm_notes)],
            change_report=changes,
            quality_findings=quality.findings,
            brief_status=status,
            verification=verification,
            context_issues=context_issues,
        )
        ranking.append(_ranking(clients[client_id], facts.facts, signals.signals, calendar))
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
        refreshed_at=manifest.created_at,
        data_health=health,
        clients=clients,
        calendar=calendar,
        ranking=sorted(ranking, key=lambda item: (-item.score, item.client_id)),
        reviews=reviews,
    )
    requested = _references(result.model_dump(mode="json"))
    evidence_ids = set()
    for identifier in requested:
        evidence_ids.update(references.get(identifier, {identifier}))
    result.connected_evidence = {
        identifier: connected_records[identifier]
        for identifier in sorted(evidence_ids)
        if identifier in connected_records
    }
    result.evidence = store.load_evidence(
        sorted(evidence_ids - result.connected_evidence.keys()), run_id=manifest.run_id
    )
    return result
