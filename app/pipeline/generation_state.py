"""Shared, serializable contracts for the artifact generation adapter."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, NotRequired, TypedDict

ProcessingMode = Literal["first_seen", "incremental_update", "no_material_change"]
FlowStatus = Literal[
    "context_ready",
    "insights_ready",
    "brief_ready",
    "verified",
    "awaiting_review",
    "approved",
    "rejected",
    "unchanged",
    "needs_confirmation",
]


class ClientFlowState(TypedDict):
    """Handoff contract shared by the three agents and deterministic nodes."""

    run_id: str
    client_id: str
    source_dir: str
    as_of: str
    previous_source_versions: NotRequired[dict[str, str]]
    source_versions: NotRequired[dict[str, str]]
    changed_sources: NotRequired[list[str]]
    processing_mode: NotRequired[ProcessingMode]
    client_context: NotRequired[dict[str, Any]]
    context_issues: NotRequired[list[str]]
    fact_bundle: NotRequired[list[dict[str, Any]]]
    evidence_map: NotRequired[dict[str, dict[str, Any]]]
    ranked_insights: NotRequired[list[dict[str, Any]]]
    draft_brief: NotRequired[dict[str, Any]]
    meeting_brief: NotRequired[dict[str, Any]]
    verification_report: NotRequired[dict[str, Any]]
    review: NotRequired[dict[str, Any]]
    dashboard_view_model: NotRequired[dict[str, Any]]
    status: NotRequired[FlowStatus]
    trace: Annotated[list[str], add]
