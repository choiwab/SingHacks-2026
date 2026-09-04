"""RM Briefing Agent: meeting-oriented language over cited artifacts."""

from __future__ import annotations

from typing import Any

from app.client_flow.state import ClientFlowState


def rm_briefing_agent(state: ClientFlowState) -> dict[str, Any]:
    """Member 2: publish the cited draft as a MeetingBrief handoff."""
    draft = state.get("draft_brief")
    if not draft:
        return {
            "context_issues": ["RM briefing received no draft"],
            "status": "needs_confirmation",
            "trace": ["rm_briefing_agent:failed"],
        }
    return {
        "meeting_brief": draft,
        "status": "brief_ready",
        "trace": ["rm_briefing_agent:complete"],
    }
