"""Run agent generation over pinned artifacts, without reopening raw source files.

The available Member 4 gate checks citation existence only. Until a complete verifier
is injected, its result is disclosed as incomplete and never grants review readiness.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, NotRequired

from langgraph.graph import END, START, StateGraph

from app.client_flow.agents.briefing import rm_briefing_agent
from app.client_flow.nodes.verification import evidence_gate
from app.client_flow.state import ClientFlowState
from app.pipeline.loaders import ArtifactStore

Node = Callable[[ClientFlowState], dict[str, Any]]


class ArtifactFlowState(ClientFlowState):
    signal_set: NotRequired[list[dict[str, Any]]]
    connected_context: NotRequired[list[dict[str, Any]]]
    memory_card: NotRequired[dict[str, Any] | None]


@dataclass(frozen=True)
class AgentHooks:
    """Dependency seam for Member 2 agents and Member 4's complete verifier."""

    context: Node | None = None
    wealth: Node | None = None
    briefing: Node = rm_briefing_agent
    verifier: Node | None = None


def _state(store: ArtifactStore, client_id: str, run_id: str) -> ArtifactFlowState:
    manifest = store.load_manifest(run_id)
    bundle = store.load_curated_bundle(client_id, run_id=run_id)
    facts = store.load_fact_bundle(client_id, run_id=run_id)
    signals = store.load_signal_set(client_id, run_id=run_id)
    changes = store.load_change_report(client_id, run_id=run_id)
    evidence = store.load_evidence_map(run_id=run_id)
    return {
        "run_id": run_id,
        "client_id": client_id,
        "as_of": bundle.as_of.isoformat(),
        "source_dir": "",
        "client_context": bundle.model_dump(mode="json"),
        "fact_bundle": [fact.model_dump(mode="json") for fact in facts.facts],
        "signal_set": [signal.model_dump(mode="json") for signal in signals.signals],
        "evidence_map": {
            identifier: record.model_dump(mode="json")
            for identifier, record in evidence.entries.items()
        },
        "processing_mode": changes.processing_mode,
        "changed_sources": changes.changed_source_files,
        "context_issues": list(manifest.context_issues),
        "ranked_insights": [],
        "connected_context": [],
        "memory_card": None,
        "trace": [],
    }


def _verify(state: ClientFlowState, verifier: Node | None) -> dict[str, Any]:
    # Adapt one-number provenance to the legacy gate's source_rows contract.
    gate_state: ClientFlowState = {
        **state,
        "fact_bundle": [
            {**fact, "source_rows": fact.get("evidence_ids", [])}
            for fact in state.get("fact_bundle", [])
        ],
    }
    result = (verifier or evidence_gate)(gate_state)
    report = dict(result.get("verification_report", {}))
    if verifier is None:
        report["citation_check_passed"] = bool(report.get("passed"))
        report["passed"] = False
        report["errors"] = [
            *report.get("errors", []),
            "Full numeric and semantic verification is not connected",
        ]
        report["verification_scope"] = "citation_existence_only"
        result = {**result, "status": "needs_confirmation"}
    return {**result, "verification_report": report}


def verify_brief(
    store: ArtifactStore,
    client_id: str,
    run_id: str,
    brief: dict[str, Any],
    *,
    verifier: Node | None = None,
    brief_version: int = 1,
) -> dict[str, Any]:
    """Synchronously reverify a complete brief or generation envelope after an edit."""
    state = _state(store, client_id, run_id)
    state["meeting_brief"] = deepcopy(brief.get("meeting_brief", brief))
    if "meeting_brief" in brief:
        state["connected_context"] = deepcopy(brief.get("connected_context", []))
        state["memory_card"] = deepcopy(brief.get("memory_card"))
        state["ranked_insights"] = deepcopy(brief.get("insights", []))
        state["context_issues"] = list(
            dict.fromkeys([*state.get("context_issues", []), *brief.get("context_issues", [])])
        )
    return {**_verify(state, verifier)["verification_report"], "brief_version": brief_version}


def execute_client(
    store: ArtifactStore,
    client_id: str,
    run_id: str,
    *,
    agents: AgentHooks | None = None,
) -> dict[str, Any]:
    """Execute generation and verification, stopping before the review-ledger boundary."""
    hooks = agents or AgentHooks()
    initial = _state(store, client_id, run_id)

    def context(state: ArtifactFlowState) -> dict[str, Any]:
        if hooks.context is not None:
            return hooks.context(state)
        return {"status": "context_ready", "trace": ["context:curated_artifacts"]}

    def wealth(state: ArtifactFlowState) -> dict[str, Any]:
        if hooks.wealth is not None:
            return hooks.wealth(state)
        return {
            "ranked_insights": [],
            "draft_brief": {
                "client_id": client_id,
                "as_of": state["as_of"],
                "sections": {
                    "summary": [],
                    "discussion_topics": [],
                    "discrepancy": [],
                    "suggested_questions": [],
                    "uncertainty": [],
                },
            },
            "status": "insights_ready",
            "context_issues": [
                *state.get("context_issues", []),
                "Agent generation is not connected",
            ],
            "trace": ["wealth:awaiting_agent_connection"],
        }

    def briefing(state: ArtifactFlowState) -> dict[str, Any]:
        return hooks.briefing(state)

    def verification(state: ArtifactFlowState) -> dict[str, Any]:
        return _verify(state, hooks.verifier)

    graph = StateGraph(ArtifactFlowState)
    graph.add_node("context", context)
    graph.add_node("wealth", wealth)
    graph.add_node("briefing", briefing)
    graph.add_node("verification", verification)
    graph.add_edge(START, "context")
    graph.add_edge("context", "wealth")
    graph.add_edge("wealth", "briefing")
    graph.add_edge("briefing", "verification")
    graph.add_edge("verification", END)
    result = graph.compile(name="curated-client-generation").invoke(initial)
    return {
        "meeting_brief": result.get("meeting_brief", {}),
        "insights": result.get("ranked_insights", []),
        "memory_card": result.get("memory_card"),
        "connected_context": result.get("connected_context", []),
        "context_issues": result.get("context_issues", []),
        "verification_report": {**result.get("verification_report", {}), "brief_version": 1},
    }
