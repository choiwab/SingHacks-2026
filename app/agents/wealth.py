"""Select precomputed signals and connect them to cited client statements."""

from typing import Any

from app.agents.contracts import Claim, CuratedClientBundle, Insight
from app.agents.state import AgentState
from app.agents.wording import rationale
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import MemoryIndex


def wealth_intelligence_agent(state: AgentState) -> dict[str, Any]:
    bundle = CuratedClientBundle.model_validate(state.get("bundle"))
    facts = {fact.id: fact for fact in bundle.facts}
    index = MemoryIndex.restore(state.get("memory_index", {}))
    records = {
        record.id: record
        for record in ConnectedContext.model_validate(state.get("connected_context")).records
    }
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
                text=facts[fact_id].what,
                citations=[fact_id],
                kind="fact",
            )
            for fact_id in signal.fact_ids
        ]
        why = rationale(
            fact_claims[0].text,
            passages[0]["text"] if passages else None,
            dataset_note=bool(
                passages and records[passages[0]["record_id"]].provenance == "dataset"
            ),
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
