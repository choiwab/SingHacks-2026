"""Three explainable signal groups using the existing priority components."""

from typing import Any

from app.analytics.scoring import build_priority


def build_signals(client_id: str, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reuse the frozen scorer, not a second set of financial formulas.

    Component scores order discussion topics, not investment recommendations or
    probabilities. The overall client priority is not copied onto every signal.
    """
    priority = build_priority(client_id, facts)
    components = priority["components"]
    by_key = {fact["id"].rsplit(":", 1)[-1]: fact for fact in facts}
    suitability_keys = ["mandate-gap", "concentration"]
    if by_key["mandate-gap"]["numbers"]["gap_pct"] == 0:
        # With no allocation breach, lead with the concentration observation, not a zero gap.
        suitability_keys.reverse()
    groups = (
        (
            "suitability",
            "conservative safe boring risk mandate concentration allocation",
            suitability_keys,
            "gap",
            "Compare the current allocation with the client's stated preferences. "
            "A mandate gap of zero is not a breach. Household look-through is a screening "
            "view, not a substitute for each portfolio's own mandate review.",
        ),
        (
            "funding",
            "tax cash funding liquidity deadline need property loan collateral",
            ["deadline", "facility"],
            "deadline",
            "Confirm the planned cash need and funding choice with the client. "
            "Daily-liquid assets are not the same as unencumbered cash available to spend.",
        ),
        (
            "portfolio-change",
            "portfolio change news market performance worried affected",
            [key for key in by_key if key.startswith("change-")],
            "consequence",
            "These are changes in position market value, not investment returns or "
            "performance attribution; trading, cash flows and FX can contribute. "
            "Any event-log match is an association, not proof of causation.",
        ),
    )
    return [
        {
            "id": f"{client_id}:signal:{key}",
            "topic": topic,
            "fact_ids": [by_key[fact_key]["id"] for fact_key in keys if fact_key in by_key],
            "score": components[component],
            "components": {component: components[component]},
            "uncertainty": (
                f"Priority uses the existing {component} component, not a probability. {disclosure}"
            ),
        }
        for key, topic, keys, component, disclosure in groups
        if any(fact_key in by_key for fact_key in keys)
    ]
