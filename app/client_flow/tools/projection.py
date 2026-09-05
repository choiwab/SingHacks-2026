"""Temporary adapter from the pipeline and analytics layers to graph artifacts.

This adapter recomputes the full book on every call and stays until Member 3's published
artifact loaders land. It selects no insights and writes no prose: ``ranked_insights`` is empty
and ``draft_brief`` is an empty shell for Member 2's agents to fill.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from app.analytics.facts import fact_engine
from app.pipeline.evidence import native
from app.pipeline.sources import load_sources


class ClientArtifacts(TypedDict):
    fact_bundle: list[dict[str, Any]]
    evidence_map: dict[str, dict[str, Any]]
    ranked_insights: list[dict[str, Any]]
    draft_brief: dict[str, Any]


def _jsonable(value: Any) -> Any:
    """Replace numpy scalars with Python natives so graph checkpoints can serialize state."""
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return native(value)


def build_client_artifacts(
    source_dir: Path,
    *,
    client_id: str,
    as_of: date,
) -> ClientArtifacts:
    """Return one client's facts and the evidence those facts cite."""
    tables, _notes = load_sources(source_dir, as_of=as_of)
    facts, evidence = fact_engine(tables, as_of)
    fact_bundle = _jsonable(facts[client_id])

    evidence_ids: set[str] = set()
    for fact in fact_bundle:
        evidence_ids.update(fact["source_rows"])
        evidence_ids.update(fact["event_ids"])
    evidence_map = {
        evidence_id: _jsonable(evidence[evidence_id])
        for evidence_id in sorted(evidence_ids)
        if evidence_id in evidence
    }
    return {
        "fact_bundle": fact_bundle,
        "evidence_map": evidence_map,
        "ranked_insights": [],
        "draft_brief": {"client_id": client_id, "sections": {}},
    }
