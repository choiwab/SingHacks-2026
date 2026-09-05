"""Fail-closed Evidence Gate for deterministic, source-backed meeting packs.

The curated loader owns financial computation. This gate checks the contract, copied values,
exact source spans and constrained wording, not arbitrary-language entailment or bank compliance.
Novel model wording or free-form edits pause for confirmation instead of receiving a false pass.
"""

from datetime import UTC, date, datetime, time

from app.agents.contracts import (
    ClientMemoryCard,
    CuratedClientBundle,
    MeetingPack,
    VerificationIssue,
    VerificationReport,
    fingerprint,
)
from app.agents.wording import (
    ALTERNATE_OPENING,
    DISCUSSION_QUESTIONS,
    OPENING,
    PRIORITIES_QUESTION,
    rationale,
)
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import MemoryIndex


def verify_meeting_pack(
    pack: MeetingPack, bundle: CuratedClientBundle, connected: ConnectedContext
) -> VerificationReport:
    issues: list[VerificationIssue] = []

    def require(condition: bool, claim_id: str, reason: str) -> None:
        if not condition:
            issues.append(VerificationIssue(claim_id=claim_id, reason=reason))

    require(
        (pack.client_id, pack.as_of) == (bundle.client_id, bundle.as_of),
        "pack",
        "Client or As-of Date differs from the curated input",
    )
    require(not bundle.quality_issues, "pack", "Curated input has blocking Data Quality Findings")
    cutoff = datetime.combine(bundle.as_of, time.max, UTC)
    require(
        all(r.client_id == bundle.client_id and r.occurred_at <= cutoff for r in connected.records),
        "pack",
        "Connected Record is outside client/date scope",
    )
    index = MemoryIndex(client_id=bundle.client_id, as_of=cutoff)
    index.update(connected.records)
    for key, expected in {
        "bundle": bundle.content_version(),
        "memory": index.version,
        "availability": fingerprint(connected.sources),
    }.items():
        require(pack.input_versions.get(key) == expected, "pack", f"Stale {key} input version")

    facts = {fact.id: fact for fact in bundle.facts}
    fact_text = {
        fact.id: bundle.fact_descriptions.get(fact.id)
        or f"{fact.kind}: {fact.value:g} {fact.currency or fact.unit}."
        for fact in bundle.facts
    }
    signals = {signal.id: signal for signal in bundle.signals}
    records = {record.id: record for record in connected.records}
    for evidence in bundle.evidence.values():
        for field in ("snapshot_date", "event_date", "note_date"):
            if evidence.record.get(field):
                try:
                    scoped = date.fromisoformat(str(evidence.record[field])) <= bundle.as_of
                except ValueError:
                    scoped = False
                require(scoped, evidence.id, f"Evidence has an invalid or future {field}")
    for fact in bundle.facts:
        require(
            bool(fact.evidence_ids)
            and set(fact.evidence_ids) <= bundle.evidence.keys()
            and any(bundle.evidence[c].source != "data/event_log.csv" for c in fact.evidence_ids),
            fact.id,
            "Fact evidence is incomplete",
        )
        require(
            all(
                c in bundle.evidence and bundle.evidence[c].source == "data/event_log.csv"
                for c in fact.evidence_ids
                if c.startswith("event_log:")
            ),
            fact.id,
            "Event explanation is not grounded in the authoritative event log",
        )

    selected = []
    seen = set()
    for signal in sorted(bundle.signals, key=lambda value: (-value.score, value.id)):
        signature = tuple(sorted(signal.fact_ids))
        if signature not in seen:
            selected.append(signal.id)
            seen.add(signature)
        if len(selected) == 3:
            break
    require(
        [insight.signal_id for insight in pack.insights] == selected,
        "insights",
        "Insight selection differs from the ranked Signal Set",
    )
    for insight in pack.insights:
        signal = signals.get(insight.signal_id)
        if signal is None:
            require(False, insight.signal_id, "Unknown Signal")
            continue
        require(
            (insight.score, insight.components) == (signal.score, signal.components),
            insight.signal_id,
            "Signal score or components were changed",
        )
        require(
            [claim.citations for claim in insight.facts] == [[key] for key in signal.fact_ids],
            insight.signal_id,
            "Signal Fact selection was changed",
        )

    # Every claim must be an exact Fact, exact record span, or an evidence-bound template.
    for claim in pack.claims():
        require(
            set(claim.citations) <= facts.keys() | bundle.evidence.keys() | index.chunks.keys(),
            claim.id,
            "Unresolved or stale citation",
        )
        cited_facts = [facts[key] for key in claim.citations if key in facts]
        chunks = [index.chunks[key] for key in claim.citations if key in index.chunks]
        allowed: set[str] = set()
        if claim.kind == "fact":
            allowed = {fact_text[fact.id] for fact in cited_facts}
        elif claim.kind == "memory":
            allowed = {chunk["text"] for chunk in chunks}
        elif claim.kind == "uncertainty":
            allowed = {
                signal.uncertainty
                for signal in bundle.signals
                if claim.id == f"uncertainty:{signal.id}" and claim.citations == signal.fact_ids
            }
            for citation in claim.citations:
                event = bundle.evidence.get(citation)
                if event and event.source == "data/event_log.csv":
                    allowed.add(
                        "Event-log association, not causal attribution: "
                        f"{event.record.get('event_date')}: {event.record.get('description')}"
                    )
        elif claim.id == "opening":
            allowed = {OPENING, ALTERNATE_OPENING}
        elif claim.id == "question:priorities":
            allowed = {PRIORITIES_QUESTION}
        else:
            for fact in cited_facts:
                if claim.id.startswith("talking_point:"):
                    allowed.add(f"Discuss: {fact_text[fact.id]}")
                elif claim.id.startswith("question:"):
                    allowed.add(DISCUSSION_QUESTIONS.get(fact.kind.split(".")[0], ""))
                elif claim.id.startswith(("insight:", "advice:")):
                    if not chunks:
                        allowed.add(rationale(fact_text[fact.id], None, dataset_note=False))
                    for chunk in chunks:
                        allowed.add(
                            rationale(
                                fact_text[fact.id],
                                chunk["text"],
                                dataset_note=records[chunk["record_id"]].provenance == "dataset",
                            )
                        )
        require(claim.text in allowed, claim.id, "Wording is not supported by the cited evidence")

    require(
        [(claim.text, claim.citations) for claim in pack.brief.summary]
        == [(claim.text, claim.citations) for insight in pack.insights for claim in insight.facts],
        "summary",
        "Summary omits or changes selected Facts",
    )
    required_uncertainty = {f"uncertainty:{key}" for key in selected}
    require(
        required_uncertainty <= {claim.id for claim in pack.brief.uncertainty},
        "uncertainty",
        "Required limitations are missing",
    )
    require(
        {f"talking_point:{key}" for key in selected}
        == {claim.id for claim in pack.brief.talking_points},
        "talking_points",
        "A selected Insight has no discussion point",
    )
    require(
        "question:priorities" in {claim.id for claim in pack.brief.questions},
        "questions",
        "Client priorities confirmation is missing",
    )
    for name in ClientMemoryCard.model_fields:
        section = getattr(pack.memory_card, name)
        require(
            bool(section.claims) or bool(section.evidence_gap),
            f"memory:{name}",
            "Empty memory section does not disclose its evidence gap",
        )
    return VerificationReport(pack_version=pack.version, passed=not issues, issues=issues)
