"""LangGraph topology for the selected-client intelligence flow."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.client_flow.agents.briefing import rm_briefing_agent
from app.client_flow.agents.context import context_agent, route_context
from app.client_flow.agents.wealth import route_intelligence, wealth_intelligence_agent
from app.client_flow.nodes.control import (
    finalize,
    human_review,
    needs_confirmation,
    reuse_verified,
)
from app.client_flow.nodes.verification import evidence_gate, route_verification
from app.client_flow.state import ClientFlowState


def build_client_flow(*, checkpointer: Any | None = None):
    """Compile three broad agents with deterministic routing and an HLI interrupt."""
    graph = StateGraph(ClientFlowState)
    graph.add_node("context_agent", context_agent)
    graph.add_node("wealth_intelligence_agent", wealth_intelligence_agent)
    graph.add_node("rm_briefing_agent", rm_briefing_agent)
    graph.add_node("evidence_gate", evidence_gate)
    graph.add_node("human_review", human_review)
    graph.add_node("finalize", finalize)
    graph.add_node("reuse_verified", reuse_verified)
    graph.add_node("needs_confirmation", needs_confirmation)

    graph.add_edge(START, "context_agent")
    graph.add_conditional_edges("context_agent", route_context)
    graph.add_conditional_edges("wealth_intelligence_agent", route_intelligence)
    graph.add_edge("rm_briefing_agent", "evidence_gate")
    graph.add_conditional_edges("evidence_gate", route_verification)
    graph.add_edge("finalize", END)
    graph.add_edge("reuse_verified", END)
    graph.add_edge("needs_confirmation", END)
    return graph.compile(
        checkpointer=checkpointer or InMemorySaver(),
        name="client-future-room",
    )
