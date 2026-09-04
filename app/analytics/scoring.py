"""Deterministic priority scorer over one client's facts.

Moved from ``app/pipeline.py`` (ADR-0002). Member 4 owns the formula. The score, its
components, and the urgency thresholds are unchanged from the monolith.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    gap: float = 1.0
    deadline: float = 1.0
    consequence: float = 1.0


DEFAULT_WEIGHTS = ScoringWeights()


def _build_priority(
    client_id: str,
    facts_by_key: dict[str, dict[str, Any]],
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> dict[str, Any]:
    # TODO(M4): the monolith also attached ``reason`` and ``citations`` taken from the
    # belief-versus-data gap and a hardcoded ``meeting`` slot from the demo policy. Both were
    # deleted with the prose layer; insight selection and narration now belong to the agents.
    mandate = facts_by_key["mandate-gap"]
    deadline = facts_by_key["deadline"]
    facility = facts_by_key.get("facility")
    concentration = facts_by_key["concentration"]
    mandate_gap = float(mandate["numbers"]["gap_pct"])
    facility_pressure = max(0, 20 - float(facility["numbers"]["gap_pct"]) * 5) if facility else 0.0
    coverage = float(deadline["numbers"].get("coverage_pct", 999))
    liquidity_pressure = max(0, 30 - min(coverage, 100) * 0.3)
    gap_size = min(100, 10 + mandate_gap * 2 + facility_pressure)
    closeness = max(8, 100 - min(float(deadline["numbers"]["days"]), 365) / 4)
    profile = facts_by_key["profile"]["numbers"]
    vulnerability = (10 - float(profile["risk_tolerance_score"])) * 3
    if "inherited" in str(profile["life_stage"]).lower():
        vulnerability += 12
    consequence = min(
        100,
        20
        + mandate_gap
        + facility_pressure * 2
        + liquidity_pressure
        + concentration["numbers"]["weight_pct"] / 4
        + vulnerability,
    )
    weighted_score = (
        gap_size**weights.gap * closeness**weights.deadline * consequence**weights.consequence
    )
    total_weight = weights.gap + weights.deadline + weights.consequence
    score = round(weighted_score ** (1 / total_weight))
    return {
        "client_id": client_id,
        "name": profile["name"],
        "score": score,
        "components": {
            "gap": round(gap_size),
            "deadline": round(closeness),
            "consequence": round(consequence),
        },
        "urgency": "now" if score >= 65 else "soon" if score >= 45 else "watch",
    }


def build_priority(
    client_id: str,
    facts: list[dict[str, Any]],
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> dict[str, Any]:
    """Score one client's fact list; ``facts`` is the list ``fact_engine`` returns per client."""
    facts_by_key = {fact["id"].rsplit(":", 1)[-1]: fact for fact in facts}
    return _build_priority(client_id, facts_by_key, weights)
