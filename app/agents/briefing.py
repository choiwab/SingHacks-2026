"""Build a cited meeting brief and Memory Card from the selected signals and passages."""

from typing import Any

from app.agents.contracts import (
    Claim,
    ClientMemoryCard,
    CuratedClientBundle,
    Insight,
    MeetingBrief,
    MeetingPack,
    MemorySection,
    fingerprint,
)
from app.agents.generation import generate
from app.agents.state import AgentState
from app.agents.wording import DISCUSSION_QUESTIONS, OPENING, PRIORITIES_QUESTION
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import MemoryIndex

TOPICS = {
    "who_they_are": "family relationship inherited portfolio",
    "personality_and_style": "communication written plain language preference",
    "stated_needs_and_goals": "tax payment safe risk priority",
    "recent_updates": "recent update",
    "open_promises": "promised follow up meeting",
}


def rm_briefing_agent(state: AgentState, *, live: bool = False) -> dict[str, Any]:
    bundle = CuratedClientBundle.model_validate(state.get("bundle"))
    index = MemoryIndex.restore(state.get("memory_index", {}))
    connected = ConnectedContext.model_validate(state.get("connected_context"))
    insights = [Insight.model_validate(value) for value in state.get("insights", [])]
    sections: dict[str, MemorySection] = {}
    searches = []
    section_versions: dict[str, str] = {}
    reused_sections = []
    previous_pack = state.get("pack")
    for topic, query in TOPICS.items():
        passages = index.search(query, topic=topic, limit=3)
        section_versions[topic] = fingerprint([item["id"] for item in passages])
        searches.append({"topic": topic, "passages": passages})
        if (
            previous_pack
            and state.get("section_versions", {}).get(topic) == section_versions[topic]
        ):
            sections[topic] = MemorySection.model_validate(previous_pack["memory_card"][topic])
            reused_sections.append(topic)
            continue
        sections[topic] = MemorySection(
            claims=[
                Claim(
                    id=f"memory:{topic}:{item['id']}",
                    text=item["text"],
                    citations=[item["id"]],
                    kind="memory",
                )
                for item in passages
            ],
            evidence_gap=None if passages else "No supporting communication record available.",
        )

    references = [insight.facts[0].citations[0] for insight in insights] or [bundle.facts[0].id]
    talking_points = [
        Claim(
            id=f"talking_point:{item.signal_id}",
            text=f"Discuss: {item.facts[0].text}",
            citations=item.facts[0].citations,
            kind="suggestion",
        )
        for item in insights
    ]
    questions = [
        Claim(
            id="question:priorities",
            text=PRIORITIES_QUESTION,
            citations=references,
            kind="suggestion",
        )
    ]
    if any(record.provenance == "dataset" for record in connected.records):
        facts = {fact.id: fact for fact in bundle.facts}
        for insight in insights:
            fact_id = insight.facts[0].citations[0]
            question = DISCUSSION_QUESTIONS.get(facts[fact_id].kind)
            if question:
                questions.append(
                    Claim(
                        id=f"question:{insight.signal_id}",
                        text=question,
                        citations=[fact_id],
                        kind="suggestion",
                    )
                )
    uncertainty = [
        Claim(
            id=f"uncertainty:{signal.id}",
            text=signal.uncertainty,
            citations=signal.fact_ids,
            kind="uncertainty",
        )
        for signal in bundle.signals
        if signal.id in {i.signal_id for i in insights}
    ]
    if any(record.provenance == "dataset" for record in connected.records):
        selected_fact_ids = {
            citation for item in insights for f in item.facts for citation in f.citations
        }
        event_ids = sorted(
            {e for fact in bundle.facts if fact.id in selected_fact_ids for e in fact.event_ids}
        )
        for event_id in event_ids:
            event = bundle.evidence[event_id].record
            uncertainty.append(
                Claim(
                    id=f"event:{event_id}",
                    text=(
                        f"Event-log association, not causal attribution: {event['event_date']}: "
                        f"{event['description']}"
                    ),
                    citations=[event_id],
                    kind="uncertainty",
                )
            )
    preferences: dict[str, list[Any]] = {}
    for record in connected.records:
        if record.preference_key:
            preferences.setdefault(record.preference_key, []).append(record)
    for key, records in sorted(preferences.items()):
        if len({r.preference_value for r in records}) <= 1:
            continue
        records.sort(key=lambda r: (r.occurred_at, r.id))
        citations = [
            chunk["id"]
            for record in records
            for chunk in index.chunks.values()
            if chunk["record_id"] == record.id
        ]
        text = (
            f"Confirm current intent: statements from {records[0].occurred_at.date()} and "
            f"{records[-1].occurred_at.date()} differ. Review the dated source messages together."
        )
        uncertainty.append(
            Claim(id=f"conflict:{key}", text=text, citations=citations, kind="uncertainty")
        )
    sections["advice_notes"] = MemorySection(
        claims=[
            item.why_it_matters.model_copy(update={"id": f"advice:{item.signal_id}"})
            for item in insights
            if any("#" in c for c in item.why_it_matters.citations)
        ],
    )
    if not sections["advice_notes"].claims:
        sections["advice_notes"].evidence_gap = "No paired memory and fact evidence available."
    pack = MeetingPack(
        client_id=bundle.client_id,
        as_of=bundle.as_of,
        input_versions=state.get("input_versions", {}),
        insights=insights,
        brief=MeetingBrief(
            summary=[
                claim.model_copy(update={"id": f"summary:{claim.id}"})
                for item in insights
                for claim in item.facts
            ],
            opening=Claim(
                id="opening",
                text=OPENING,
                citations=references,
                kind="suggestion",
            ),
            talking_points=talking_points,
            questions=questions,
            uncertainty=uncertainty,
        ),
        memory_card=ClientMemoryCard(**sections),
    )
    pack, note = generate(
        pack, evidence={"bundle": bundle.model_dump(mode="json"), "passages": searches}, live=live
    )
    history = list(state.get("history", []))
    previous = state.get("pack")
    if (
        previous
        and previous["client_id"] == pack.client_id
        and previous != pack.model_dump(mode="json")
    ):
        history.append({"pack": previous, "status": state.get("prior_status", "unknown")})
    return {
        "section_versions": section_versions,
        "pack": pack.model_dump(mode="json"),
        "pack_version": pack.version,
        "history": history,
        "verification": None,
        "status": "brief_ready",
        "generation_note": note,
        "trace": [
            {
                "node": "briefing",
                "result": "complete",
                "pack_version": pack.version,
                "generation": note,
                "reused_memory_sections": reused_sections,
                "retrievals": searches,
            }
        ],
    }
