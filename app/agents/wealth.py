"""Select precomputed signals and connect them to cited client statements."""

from typing import Any

from app.agents.contracts import Claim, CuratedClientBundle, Insight
from app.agents.phase_a import phase_a_fact_description
from app.agents.policy import selected_signals, signal_rationale
from app.agents.state import AgentState
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
    searches = []
    for signal in selected_signals(bundle):
        passages = index.search(signal.topic, topic="stated_needs_and_goals", limit=1)
        searches.append({"query": signal.topic, "passages": passages})
        fact_claims = [
            Claim(
                id=f"insight:{signal.id}:{fact_id}",
                text=phase_a_fact_description(facts[fact_id])
                if not facts[fact_id].formula_id.startswith(("legacy.", "fixture.legacy."))
                else bundle.fact_descriptions.get(fact_id)
                or f"{facts[fact_id].kind}: {facts[fact_id].value:g} "
                f"{facts[fact_id].currency or facts[fact_id].unit}.",
                citations=[fact_id],
                kind="fact",
            )
            for fact_id in signal.fact_ids
        ]
        why = signal_rationale(
            signal,
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
