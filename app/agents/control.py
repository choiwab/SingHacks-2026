"""Version-aware joint review and terminal routes; persistence is an injected callback."""

from collections.abc import Callable
from typing import Any, Literal

from langgraph.types import Command, interrupt
from pydantic import ValidationError

from app.agents.contracts import MeetingPack, ReviewAction, fingerprint
from app.agents.state import AgentState


def human_review(
    state: AgentState,
    *,
    check_current: Callable[[AgentState], bool] | None = None,
) -> Command[Literal["context", "verify", "finalize", "needs_confirmation"]]:
    pack = MeetingPack.model_validate(state.get("pack"))
    report = state.get("verification")
    if not report or not report["passed"] or report["pack_version"] != pack.version:
        raise ValueError("Only the exact verified meeting pack can enter review")
    payload = {
        "kind": "meeting_pack_review",
        "client_id": pack.client_id,
        "pack_version": pack.version,
        "pack": pack.model_dump(mode="json"),
        "allowed_actions": ["Approve", "Edit", "Reject", "Flag"],
        "editable_claim_ids": [
            pack.brief.opening.id,
            *[c.id for c in pack.brief.talking_points],
        ],
    }
    editable = {c.id: c for c in [pack.brief.opening, *pack.brief.talking_points]}
    while True:
        raw = interrupt(payload)
        try:
            decision = ReviewAction.model_validate(raw)
            if decision.client_id != pack.client_id or decision.pack_version != pack.version:
                raise ValueError("Review targets a different client or stale pack version")
            if decision.action == "Edit" and not decision.changes.keys() <= editable.keys():
                raise ValueError("Only the opening and talking points may be edited")
            if decision.action == "Flag" and decision.claim_id not in {c.id for c in pack.claims()}:
                raise ValueError("Correction flag targets an unknown claim")
            break
        except ValidationError:
            payload["validation_error"] = "Invalid review fields"
        except ValueError as exc:
            payload["validation_error"] = str(exc)
    update: dict[str, Any] = {}
    # Check AFTER interrupt resumes: durable sources may have changed while the RM was away.
    if check_current and not check_current(state):
        return Command(
            update={
                "trace": [{"node": "human_review", "result": "inputs_changed_refresh_required"}]
            },
            goto="context",
        )
    route = "finalize"
    if decision.action == "Edit":
        history = [
            *state.get("history", []),
            {"pack": pack.model_dump(mode="json"), "status": "awaiting_review"},
        ]
        for key, value in decision.changes.items():
            editable[key].text = value
            editable[key].authorship = "rm"
        update = {
            "pack": pack.model_dump(mode="json"),
            "pack_version": pack.version,
            "history": history,
            "verification": None,
            "status": "brief_ready",
        }
        route = "verify"
    elif decision.action == "Flag":
        update = {"issues": [f"Correction requested for {decision.claim_id}: {decision.reason}"]}
        route = "needs_confirmation"
    review = decision.model_dump(mode="json")
    event = {"event_id": fingerprint(review), **review}
    return Command(
        update={
            **update,
            "review": review,
            "review_events": [*state.get("review_events", []), event],
            "trace": [
                {
                    "node": "human_review",
                    "action": decision.action,
                    "pack_version": decision.pack_version,
                }
            ],
        },
        goto=route,
    )


def finalize(state: AgentState) -> dict[str, Any]:
    review = state.get("review") or {}
    approved = review.get("action") == "Approve"
    return {
        "status": "approved" if approved else "rejected",
        "last_approved": state.get("pack") if approved else state.get("last_approved"),
        "trace": [{"node": "finalize", "result": "approved" if approved else "rejected"}],
    }


def reuse(state: AgentState) -> dict[str, Any]:
    # Reuse the actual previous status. Unchanged is not equivalent to approved.
    status = state.get("prior_status", "needs_confirmation")
    return {"status": status, "trace": [{"node": "reuse", "result": status}]}


def needs_confirmation(state: AgentState) -> dict[str, Any]:
    return {
        "status": "needs_confirmation",
        "trace": [{"node": "stop", "result": "needs_confirmation"}],
    }


def publish_reviews(state: AgentState, sink: Callable[[dict[str, Any]], None] | None) -> None:
    """Member 3's optional sink must upsert by event_id for checkpoint/retry safety."""
    if sink:
        for event in state.get("review_events", []):
            sink(event)
