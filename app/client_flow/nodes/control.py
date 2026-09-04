"""Human review and terminal control nodes owned by graph orchestration."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.types import Command, interrupt
from pydantic import ValidationError

from app.client_flow.state import ClientFlowState, FlowStatus
from app.monday_brief.models import ReviewRequest


def human_review(
    state: ClientFlowState,
) -> Command[Literal["evidence_gate", "finalize"]]:
    """Member 4: pause for the RM's approve, edit, or reject decision."""
    meeting_brief = state.get("meeting_brief")
    if not meeting_brief:
        raise ValueError("RM review requires a meeting brief")
    raw = interrupt(
        {
            "kind": "rm_review",
            "client_id": state["client_id"],
            "allowed_actions": ["Approve", "Edit", "Reject"],
            "meeting_brief": meeting_brief,
        }
    )
    try:
        decision = ReviewRequest.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid RM review: {exc}") from exc
    if decision.client_id != state["client_id"]:
        raise ValueError("RM review client does not match the active graph client")

    review = decision.model_dump(mode="json")
    if decision.action == "Edit":
        if not decision.text.strip():
            raise ValueError("An Edit review requires replacement opening text")
        brief = dict(meeting_brief)
        brief["opening"] = {**brief["opening"], "text": decision.text}
        return Command(
            update={
                "meeting_brief": brief,
                "review": review,
                "status": "brief_ready",
                "trace": ["human_review:edit"],
            },
            goto="evidence_gate",
        )

    return Command(
        update={
            "review": review,
            "status": "awaiting_review",
            "trace": [f"human_review:{decision.action.lower()}"],
        },
        goto="finalize",
    )


def finalize(state: ClientFlowState) -> dict[str, Any]:
    """Member 4: expose only the reviewed result to the dashboard boundary."""
    review = state.get("review", {})
    approved = review.get("action") == "Approve"
    status: FlowStatus = "approved" if approved else "rejected"
    return {
        "dashboard_view_model": {
            "client_id": state["client_id"],
            "as_of": state["as_of"],
            "status": status,
            "insights": state.get("ranked_insights", []),
            "meeting_brief": state.get("meeting_brief") if approved else None,
            "verification": state.get("verification_report", {}),
            "review": review,
        },
        "status": status,
        "trace": [f"finalize:{status}"],
    }


def reuse_verified(state: ClientFlowState) -> dict[str, Any]:
    """Keep prior reviewed content when source fingerprints have not changed."""
    return {
        "dashboard_view_model": {
            "client_id": state["client_id"],
            "as_of": state["as_of"],
            "status": "unchanged",
            "insights": state.get("ranked_insights", []),
            "meeting_brief": state.get("meeting_brief"),
        },
        "status": "unchanged",
        "trace": ["reuse_verified:complete"],
    }


def needs_confirmation(state: ClientFlowState) -> dict[str, Any]:
    """Stop unsupported output before it reaches RM approval."""
    issues = [
        *state.get("context_issues", []),
        *state.get("verification_report", {}).get("errors", []),
    ]
    return {
        "dashboard_view_model": {
            "client_id": state["client_id"],
            "as_of": state["as_of"],
            "status": "needs_confirmation",
            "issues": list(dict.fromkeys(issues)),
        },
        "status": "needs_confirmation",
        "trace": ["needs_confirmation:stop"],
    }
