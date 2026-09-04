"""Sample adapter from the existing deterministic pipeline to graph artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from app.client_flow.tools.evidence import collect_citations
from app.monday_brief import build_monday_brief


class ClientArtifacts(TypedDict):
    fact_bundle: list[dict[str, Any]]
    evidence_map: dict[str, dict[str, Any]]
    ranked_insights: list[dict[str, Any]]
    draft_brief: dict[str, Any]


def build_client_artifacts(
    source_dir: Path,
    *,
    client_id: str,
    as_of: date,
) -> ClientArtifacts:
    """Build sample selected-client artifacts with the repository's current pipeline."""
    # The current builder computes the full book. Replace this adapter with narrower
    # Member 2 tools only if demo latency becomes a problem.
    projection = build_monday_brief(source_dir, as_of=as_of)
    facts = [fact.model_dump(mode="json") for fact in projection.facts[client_id]]
    priority = next(item for item in projection.ranking if item.client_id == client_id)
    brief = projection.pre_reads[client_id].model_dump(mode="json")
    insights = [
        {
            "text": priority.reason,
            "citations": priority.citations,
            "score": priority.score,
            "urgency": priority.urgency,
        },
        *brief["rules_money"][:2],
    ][:3]

    fact_ids = {fact["id"] for fact in facts}
    evidence_ids = collect_citations([insights, brief]) - fact_ids
    for fact in facts:
        evidence_ids.update(fact["source_rows"])
        evidence_ids.update(fact["event_ids"])
    evidence = {
        evidence_id: projection.evidence[evidence_id].model_dump(mode="json")
        for evidence_id in sorted(evidence_ids)
        if evidence_id in projection.evidence
    }
    return {
        "fact_bundle": facts,
        "evidence_map": evidence,
        "ranked_insights": insights,
        "draft_brief": brief,
    }
