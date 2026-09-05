"""Three-agent graph with explicit data-team integration boundaries."""

from collections.abc import Callable
from functools import partial
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.briefing import rm_briefing_agent
from app.agents.context import BundleLoader, CommunicationLoader, context_agent, route_context
from app.agents.contracts import CuratedClientBundle, MeetingPack, VerificationReport
from app.agents.control import finalize, human_review, needs_confirmation, publish_reviews, reuse
from app.agents.state import AgentState
from app.agents.wealth import wealth_intelligence_agent
from app.mcp.records import ConnectedContext

Verifier = Callable[[MeetingPack, CuratedClientBundle, ConnectedContext], VerificationReport]


def build_agent_flow(
    *,
    load_bundle: BundleLoader,
    load_communications: CommunicationLoader,
    verify_pack: Verifier,
    record_review: Callable[[dict[str, Any]], None] | None = None,
    checkpointer: Any | None = None,
    live_generation: bool = False,
):
    """No default passing gate: Member 4 must supply the verifier (or a labelled test double)."""

    load_context = partial(
        context_agent,
        load_bundle=load_bundle,
        load_communications=load_communications,
        generation_policy="v1:openai" if live_generation else "v1:deterministic",
    )

    def inputs_current(state: AgentState) -> bool:
        current = load_context(state)
        return not current.get("context_failed") and current.get("input_versions") == state.get(
            "input_versions"
        )

    def verify(state: AgentState) -> dict[str, Any]:
        publish_reviews(state, record_review)
        pack = MeetingPack.model_validate(state.get("pack"))
        try:
            report = VerificationReport.model_validate(
                verify_pack(
                    pack.model_copy(deep=True),
                    CuratedClientBundle.model_validate(state.get("bundle")),
                    ConnectedContext.model_validate(state.get("connected_context")),
                )
            )
            if report.pack_version != pack.version:
                raise ValueError("Verification targets a stale pack")
        except (ValueError, OSError):
            return {
                "verification": None,
                "status": "needs_confirmation",
                "issues": ["Verifier unavailable or invalid report"],
                "trace": [{"node": "verify", "result": "unavailable"}],
            }
        return {
            "verification": report.model_dump(mode="json"),
            "status": "awaiting_review" if report.passed else "needs_confirmation",
            "issues": [f"{issue.claim_id}: {issue.reason}" for issue in report.issues],
            "trace": [
                {
                    "node": "verify",
                    "result": "pass" if report.passed else "fail",
                    "pack_version": pack.version,
                }
            ],
        }

    def finish(state: AgentState) -> dict[str, Any]:
        publish_reviews(state, record_review)
        return finalize(state)

    def stop(state: AgentState) -> dict[str, Any]:
        publish_reviews(state, record_review)
        return needs_confirmation(state)

    graph = StateGraph(AgentState)
    graph.add_node("context", load_context)
    graph.add_node("wealth", wealth_intelligence_agent)
    graph.add_node("briefing", partial(rm_briefing_agent, live=live_generation))
    graph.add_node("verify", verify)
    graph.add_node("human_review", partial(human_review, check_current=inputs_current))
    graph.add_node("finalize", finish)
    graph.add_node("needs_confirmation", stop)
    graph.add_node("reuse", reuse)
    graph.add_edge(START, "context")
    graph.add_conditional_edges("context", route_context, ["needs_confirmation", "reuse", "wealth"])
    graph.add_edge("wealth", "briefing")
    graph.add_edge("briefing", "verify")
    graph.add_conditional_edges(
        "verify",
        lambda s: "human_review" if s["status"] == "awaiting_review" else "needs_confirmation",
        ["human_review", "needs_confirmation"],
    )
    graph.add_conditional_edges(
        "reuse",
        lambda s: "human_review" if s["status"] == "awaiting_review" else END,
        ["human_review", END],
    )
    for node in ("finalize", "needs_confirmation"):
        graph.add_edge(node, END)
    return graph.compile(
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
        name="client-future-room-agents",
    )
