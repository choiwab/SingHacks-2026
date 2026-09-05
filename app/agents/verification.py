"""Fail-closed Evidence Gate for source-backed, constrained meeting preparation.

Financial values come from the curated pipeline. This gate checks typed lineage,
copied values, exact source spans and canonical discussion wording. It does not
recompute financial results, establish arbitrary-language entailment or certify
bank compliance, suitability, or human approval.
"""

import re
from datetime import UTC, date, datetime, time

from app.agents.briefing import rm_briefing_agent
from app.agents.contracts import (
    CuratedClientBundle,
    MeetingPack,
    VerificationIssue,
    VerificationReport,
    fingerprint,
)
from app.agents.phase_a import LIMITATIONS, phase_a_fact_description
from app.agents.policy import SIGNAL_DISCLOSURES
from app.agents.wealth import wealth_intelligence_agent
from app.agents.wording import ALTERNATE_OPENING, OPENING
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import MemoryIndex

OBSERVATION_DATES = (
    "snapshot_date",
    "event_date",
    "note_date",
    "acquired_date",
    "valuation_date",
    "trade_date",
    "settlement_date",
    "effective_as_of",
)
PHASE_A_PRIORITY = {"low": 20, "medium": 50, "high": 80, "critical": 100}


def _legacy(bundle: CuratedClientBundle) -> bool:
    return (
        not bundle.pipeline_run_id
        and not any(signal.kind for signal in bundle.signals)
        and all(fact.formula_id.startswith(("legacy.", "fixture.legacy.")) for fact in bundle.facts)
    )


def _canonical_payload(pack: MeetingPack) -> dict:
    result = pack.model_copy(deep=True)
    result.generation_mode = "deterministic"
    for claim in result.claims():
        claim.authorship = "agent"
    if result.brief.opening.text == ALTERNATE_OPENING:
        result.brief.opening.text = OPENING
    return result.model_dump(mode="json")


def verify_meeting_pack(
    pack: MeetingPack, bundle: CuratedClientBundle, connected: ConnectedContext
) -> VerificationReport:
    issues: list[VerificationIssue] = []
    pack_version = pack.version

    def require(condition: bool, claim_id: str, reason: str) -> None:
        if not condition:
            issues.append(VerificationIssue(claim_id=claim_id, reason=reason))

    def report() -> VerificationReport:
        return VerificationReport(pack_version=pack_version, passed=not issues, issues=issues)

    try:
        pack = MeetingPack.model_validate(pack.model_dump(mode="json"))
        bundle = CuratedClientBundle.model_validate(bundle.model_dump(mode="json"))
        connected = ConnectedContext.model_validate(connected.model_dump(mode="json"))
    except (ValueError, TypeError, AttributeError):
        require(False, "pack", "Meeting pack or input contract is invalid")
        return report()

    require(
        (pack.client_id, pack.as_of) == (bundle.client_id, bundle.as_of),
        "pack",
        "Client or As-of Date differs from the curated input",
    )
    require(
        not bundle.quality_issues
        and not any(finding.severity == "error" for finding in bundle.quality_findings),
        "pack",
        "Curated input has blocking Data Quality Findings",
    )
    cutoff = datetime.combine(bundle.as_of, time.max, UTC)
    require(
        all(
            record.client_id == bundle.client_id and record.occurred_at <= cutoff
            for record in connected.records
        ),
        "pack",
        "Connected Record is outside client/date scope",
    )
    require(
        len({record.id for record in connected.records}) == len(connected.records),
        "pack",
        "Connected Record identifiers must be unique",
    )
    for evidence in bundle.evidence.values():
        for row in (evidence.record, evidence.fields):
            require(
                row.get("client_id") in (None, "", bundle.client_id),
                evidence.id,
                "Evidence belongs to another Client",
            )
            for field in OBSERVATION_DATES:
                if row.get(field):
                    try:
                        scoped = date.fromisoformat(str(row[field])) <= bundle.as_of
                    except ValueError:
                        scoped = False
                    require(scoped, evidence.id, f"Evidence has an invalid or future {field}")

    legacy = _legacy(bundle)
    if not legacy:
        expected_notes = {
            f"notes:{entry.record['note_id']}"
            for entry in bundle.evidence.values()
            if entry.kind == "rm_notes" and entry.record.get("note_id")
        }
        require(
            expected_notes
            == {record.id for record in connected.records if record.provenance == "dataset"},
            "memory",
            "Dataset notes are missing or differ from the pinned note set",
        )
        for record in connected.records:
            if record.provenance != "dataset":
                continue
            note_id = record.id.removeprefix("notes:")
            evidence = bundle.evidence.get(f"rm_notes:{note_id}")
            require(
                record.source == "notes"
                and evidence is not None
                and evidence.kind == "rm_notes"
                and evidence.source.startswith("data/")
                and evidence.source.endswith("/rm_notes.json")
                and record.based_on == [f"{evidence.source}:{note_id}"]
                and record.text == evidence.record.get("note")
                and record.occurred_at.date().isoformat() == evidence.record.get("note_date"),
                record.id,
                "Dataset note differs from its pinned source Evidence",
            )
    facts = {fact.id: fact for fact in bundle.facts}
    for fact in bundle.facts:
        require(
            bool(fact.evidence_ids)
            and set(fact.evidence_ids) <= bundle.evidence.keys()
            and any(
                bundle.evidence[key].source != "data/event_log.csv" for key in fact.evidence_ids
            ),
            fact.id,
            "Fact evidence is incomplete",
        )
        require(
            all(
                bundle.evidence[key].source == "data/event_log.csv"
                for key in fact.evidence_ids
                if key.startswith("event_log:")
            ),
            fact.id,
            "Event explanation is not grounded in the authoritative event log",
        )
        if not legacy:
            require(
                fact.formula_id == f"phase-a-rm-review-v1.{fact.kind}"
                and re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", fact.kind) is not None,
                fact.id,
                "Fact formula lineage does not match its Phase A kind",
            )
            require(
                fact.unit in {"number", "days", "currency", "percent", "percentage_points", "ratio"}
                and (
                    bool(fact.currency and re.fullmatch(r"[A-Z]{3}", fact.currency))
                    if fact.unit == "currency"
                    else fact.currency is None
                )
                and (not fact.kind.endswith("_pct") or fact.unit == "percent")
                and (not fact.kind.endswith("_pp") or fact.unit == "percentage_points")
                and (not fact.kind.endswith("_days") or fact.unit == "days")
                and (not fact.kind.endswith("_x") or fact.unit == "ratio")
                and (not fact.kind.endswith(("_base", "_usd")) or fact.unit == "currency")
                and (not fact.kind.endswith("_usd") or fact.currency == "USD")
                and (fact.kind != "collateral.lending_value" or fact.unit == "currency")
                and (fact.kind != "collateral.consecutive_increases" or fact.unit == "number"),
                fact.id,
                "Fact unit or currency is inconsistent with its lineage",
            )
            require(
                fact.id not in bundle.fact_descriptions
                or bundle.fact_descriptions[fact.id] == phase_a_fact_description(fact),
                fact.id,
                "Fact description differs from its deterministic value and unit",
            )

    for signal in bundle.signals:
        require(
            bool(signal.components)
            and all(0 <= value <= 100 for value in signal.components.values()),
            signal.id,
            "Signal score components are invalid",
        )
        if not legacy:
            require(
                signal.kind in SIGNAL_DISCLOSURES
                and signal.id.startswith(f"{bundle.client_id}:signal:{signal.kind}")
                and signal.topic == signal.kind.replace("_", " ").replace(".", " ")
                and signal.uncertainty == LIMITATIONS,
                signal.id,
                "Signal definition or limitations differ from the frozen Phase A policy",
            )
            require(
                signal.severity in PHASE_A_PRIORITY
                and signal.score == PHASE_A_PRIORITY.get(signal.severity)
                and signal.components == {"severity_policy": signal.score},
                signal.id,
                "Signal score does not match the frozen severity policy",
            )
            require(
                bool(signal.kind)
                and bool(signal.evidence_ids)
                and set(signal.evidence_ids) <= bundle.evidence.keys()
                and {key for fact_id in signal.fact_ids for key in facts[fact_id].evidence_ids}
                <= set(signal.evidence_ids),
                signal.id,
                "Signal Evidence does not cover its selected Facts",
            )

    if issues:
        return report()

    index = MemoryIndex(client_id=bundle.client_id, as_of=cutoff)
    try:
        index.update(connected.records)
    except ValueError:
        require(False, "memory", "Connected Record provenance is conflicting")
        return report()
    for key, expected in {
        "bundle": bundle.content_version(),
        "memory": index.version,
        "availability": fingerprint(connected.sources),
    }.items():
        require(pack.input_versions.get(key) == expected, "pack", f"Stale {key} input version")

    reference_bundle = bundle.model_copy(deep=True)
    if not legacy:
        reference_bundle.fact_descriptions = {
            fact.id: phase_a_fact_description(fact) for fact in reference_bundle.facts
        }
    state = {
        "bundle": reference_bundle.model_dump(mode="json"),
        "connected_context": connected.model_dump(mode="json"),
        "memory_index": index.snapshot(),
        "input_versions": pack.input_versions,
    }
    try:
        state.update(wealth_intelligence_agent(state))
        expected = MeetingPack.model_validate(rm_briefing_agent(state, live=False)["pack"])
    except (ValueError, KeyError, TypeError, AttributeError):
        require(False, "pack", "Canonical derivation is unavailable for these inputs")
        return report()

    expected_claims = {claim.id: claim for claim in expected.claims()}
    actual_claims = {claim.id: claim for claim in pack.claims()}
    require(
        actual_claims.keys() == expected_claims.keys(),
        "pack",
        "Required claims, disclosures or Information Requests were omitted or added",
    )
    for claim_id in sorted(actual_claims.keys() & expected_claims.keys()):
        actual = actual_claims[claim_id].model_dump(exclude={"authorship"})
        target = expected_claims[claim_id].model_dump(exclude={"authorship"})
        if claim_id == "opening" and actual["text"] == ALTERNATE_OPENING:
            actual["text"] = OPENING
        require(
            actual == target,
            claim_id,
            "Wording, Fact selection or citations differ from the canonical source derivation",
        )
    require(
        _canonical_payload(pack) == _canonical_payload(expected),
        "pack",
        "Meeting sections, ranked Insights or required disclosures differ from policy",
    )
    return report()
