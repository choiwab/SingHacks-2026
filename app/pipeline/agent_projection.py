"""Project a pinned pipeline run to agent inputs without recomputing financial values."""

from app.agents.contracts import ChangeReport, CuratedClientBundle, fingerprint
from app.agents.phase_a import phase_a_fact_description, phase_a_signal
from app.pipeline.loaders import ArtifactStore


def project_agent_bundle(store: ArtifactStore, client_id: str, run_id: str) -> CuratedClientBundle:
    manifest = store.load_manifest(run_id)
    if client_id not in manifest.client_ids:
        raise ValueError(f"Unknown client: {client_id}")
    facts = store.load_fact_bundle(client_id, run_id=run_id)
    signals = store.load_signal_set(client_id, run_id=run_id)
    evidence = store.load_evidence_map(run_id=run_id)
    quality = store.load_data_quality_report(run_id=run_id, client_id=client_id)
    changes = store.load_change_report(client_id, run_id=run_id)
    curated = store.load_curated_bundle(client_id, run_id=run_id)
    mandate_codes = {portfolio.mandate_code for portfolio in curated.portfolios}
    scoped_findings = []
    for finding in quality.findings:
        scoped_ids = []
        for identifier in finding.evidence_ids:
            entry = evidence.entries[identifier]
            if entry.record.get("client_id") not in (None, client_id):
                continue
            if entry.kind == "mandates" and entry.record.get("mandate_code") not in mandate_codes:
                continue
            scoped_ids.append(identifier)
        if finding.evidence_ids and not scoped_ids:
            continue
        scoped_findings.append(
            finding.model_copy(
                update={
                    "evidence_ids": scoped_ids or [f"clients:{client_id}"],
                }
            )
        )
    referenced = (
        {key for fact in facts.facts for key in fact.evidence_ids}
        | {key for signal in signals.signals for key in signal.evidence_ids}
        | {key for finding in scoped_findings for key in finding.evidence_ids}
    )
    mapped = [phase_a_signal(signal) for signal in signals.signals]
    payload = {
        "client_id": client_id,
        "as_of": manifest.as_of.isoformat(),
        "facts": [fact.model_dump(mode="json") for fact in facts.facts],
        "fact_descriptions": {fact.id: phase_a_fact_description(fact) for fact in facts.facts},
        "signals": [signal.model_dump(mode="json") for signal in mapped],
        "quality_findings": [finding.model_dump(mode="json") for finding in scoped_findings],
        "evidence": {
            key: evidence.entries[key].model_dump(mode="json") for key in sorted(referenced)
        },
        "quality_issues": [
            finding.message for finding in scoped_findings if finding.severity == "error"
        ],
    }
    version = fingerprint(payload)
    for identifier, entry in evidence.entries.items():
        if entry.kind == "rm_notes" and entry.record.get("client_id") == client_id:
            payload["evidence"][identifier] = entry.model_dump(mode="json")
    return CuratedClientBundle.model_validate(
        {
            **payload,
            "version": version,
            "pipeline_run_id": run_id,
            "change_report": ChangeReport(
                previous_version=changes.prior_run_id,
                changed_fact_ids=changes.changed_fact_ids,
                changed_signal_ids=changes.affected_signal_ids,
            ),
        }
    )
