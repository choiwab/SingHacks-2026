"""Wealth Intelligence Agent: facts, discrepancies, and insight ranking."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from app.client_flow.state import ClientFlowState
from app.client_flow.tools.projection import build_client_artifacts
from app.wealth_intelligence import ProjectionBuildError


def wealth_intelligence_agent(state: ClientFlowState) -> dict[str, Any]:
    """Member 3 sample: call deterministic tools and expose selected-client artifacts."""
    try:
        artifacts = build_client_artifacts(
            Path(state["source_dir"]),
            client_id=state["client_id"],
            as_of=date.fromisoformat(state["as_of"]),
        )
    except ProjectionBuildError as exc:
        return {
            "context_issues": [str(item) for item in exc.diagnostics],
            "status": "needs_confirmation",
            "trace": ["wealth_intelligence_agent:failed"],
        }

    return {
        **artifacts,
        "status": "insights_ready",
        "trace": ["wealth_intelligence_agent:complete"],
    }


def route_intelligence(
    state: ClientFlowState,
) -> Literal["rm_briefing_agent", "needs_confirmation"]:
    return "needs_confirmation" if state.get("context_issues") else "rm_briefing_agent"
