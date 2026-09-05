"""Select precomputed signals and connect them to cited client statements."""

from typing import Any

from app.agents.contracts import Claim, CuratedClientBundle, Insight
from app.agents.state import AgentState
from app.mcp.retrieval import MemoryIndex


def wealth_intelligence_agent(state: AgentState) -> dict[str, Any]:
    bundle = CuratedClientBundle.model_validate(state.get("bundle"))
    facts = {fact.id: fact for fact in bundle.facts}
    index = MemoryIndex.restore(state.get("memory_index", {}))
    insights: list[Insight] = []
    seen: set[tuple[str, ...]] = set()
    searches = []
    for signal in sorted(bundle.signals, key=lambda s: (-s.score, s.id)):
        signature = tuple(sorted(signal.fact_ids))
        if signature in seen:
            continue
        seen.add(signature)
        passages = index.search(signal.topic, topic="stated_needs_and_goals", limit=1)
        searches.append({"query": signal.topic, "passages": passages})
        fact_claims = [
            Claim(
                id=f"insight:{signal.id}:{fact_id}",
                text=bundle.fact_descriptions.get(fact_id)
                or f"{facts[fact_id].kind}: {facts[fact_id].value:g} "
                f"{facts[fact_id].currency or facts[fact_id].unit}.",
                citations=[fact_id],
                kind="fact",
            )
            for fact_id in signal.fact_ids
        ]
        why = (
            f'Ask how this relates to the client statement: "{passages[0]["text"]}"'
            if passages
            else "Ask the client how this finding relates to their current priorities."
        )
        citations = [*signal.fact_ids, *([passages[0]["id"]] if passages else [])]
        insights.append(
            Insight(
                signal_id=signal.id,
                score=signal.score,
                components=signal.components,
                facts=fact_claims,
                why_it_matters=Claim(
                    id=f"insight:{signal.id}:why", text=why, citations=citations, kind="suggestion"
                ),
            )
        )
        if len(insights) == 3:
            break
    return {
        "insights": [item.model_dump(mode="json") for item in insights],
        "status": "insights_ready",
        "trace": [
            {
                "node": "wealth",
                "result": "complete",
                "selected_signals": [item.signal_id for item in insights],
                "retrievals": searches,
            }
        ],
    }
