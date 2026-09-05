"""Preserved legacy pre-read gate; not a verifier for the new MeetingPack contract."""

from __future__ import annotations

from typing import Any, Literal

from app.pipeline.evidence import collect_citations


def _cited_items(brief: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten every generated claim under ``brief["sections"]``; each must carry citations."""
    items: list[dict[str, Any]] = []
    for section in brief.get("sections", {}).values():
        for item in section if isinstance(section, list) else [section]:
            if isinstance(item, dict):
                items.append(item)
    return items


def evidence_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Member 4: block briefs with uncited claims or unresolved evidence."""
    brief = state.get("meeting_brief", {})
    facts = {fact["id"]: fact for fact in state.get("fact_bundle", [])}
    evidence = state.get("evidence_map", {})
    cited_items = _cited_items(brief)
    missing_citations = [
        index for index, item in enumerate(cited_items) if not item.get("citations")
    ]
    unresolved = sorted(
        citation
        for citation in collect_citations(cited_items)
        if citation not in facts and citation not in evidence
    )
    ungrounded_facts = sorted(
        fact["id"]
        for fact in facts.values()
        if any(
            citation not in evidence
            for citation in [*fact.get("source_rows", []), *fact.get("event_ids", [])]
        )
    )
    errors = [
        *(f"brief item {index} has no citation" for index in missing_citations),
        *(f"unresolved citation: {citation}" for citation in unresolved),
        *(f"ungrounded fact: {fact_id}" for fact_id in ungrounded_facts),
    ]
    passed = not errors
    return {
        "verification_report": {
            "passed": passed,
            "errors": errors,
            "as_of": state["as_of"],
        },
        "status": "verified" if passed else "needs_confirmation",
        "trace": [f"evidence_gate:{'pass' if passed else 'fail'}"],
    }


def route_verification(
    state: dict[str, Any],
) -> Literal["human_review", "needs_confirmation"]:
    report = state.get("verification_report", {})
    return "human_review" if report.get("passed") else "needs_confirmation"
