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
    referenced = {key for fact in facts.facts for key in fact.evidence_ids} | {
        key for signal in signals.signals for key in signal.evidence_ids
    }
    warnings = list(
        dict.fromkeys(
            finding.message for finding in quality.findings if finding.severity == "warning"
        )
    )
    mapped = [phase_a_signal(signal) for signal in signals.signals]
    if warnings:
        for signal in mapped:
            signal.uncertainty += " Source limitations: " + "; ".join(warnings)
    payload = {
        "client_id": client_id,
        "as_of": manifest.as_of.isoformat(),
        "facts": [fact.model_dump(mode="json") for fact in facts.facts],
        "fact_descriptions": {fact.id: phase_a_fact_description(fact) for fact in facts.facts},
        "signals": [signal.model_dump(mode="json") for signal in mapped],
        "evidence": {
            key: evidence.entries[key].model_dump(mode="json") for key in sorted(referenced)
        },
        "quality_issues": [
            finding.message for finding in quality.findings if finding.severity == "error"
        ],
    }
    return CuratedClientBundle.model_validate(
        {
            **payload,
            "version": fingerprint(payload),
            "change_report": ChangeReport(
                previous_version=changes.prior_run_id,
                changed_fact_ids=changes.changed_fact_ids,
                changed_signal_ids=changes.affected_signal_ids,
            ),
        }
    )
