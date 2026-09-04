"""Context Agent: source loading, validation, and change classification."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from app.client_flow.state import ClientFlowState, ProcessingMode
from app.client_flow.tools.sources import load_client_record, source_versions


def context_agent(state: ClientFlowState) -> dict[str, Any]:
    """Member 2: validate the request, fingerprint sources, and choose processing mode."""
    source_dir = Path(state["source_dir"])
    client_id = state["client_id"]
    versions, issues = source_versions(source_dir)
    client = load_client_record(source_dir, client_id)
    if client is None:
        issues.append(f"clients.csv: {client_id} does not exist")
    try:
        date.fromisoformat(state["as_of"])
    except ValueError:
        issues.append("as_of: expected YYYY-MM-DD")

    previous = state.get("previous_source_versions", {})
    changed = sorted(name for name, version in versions.items() if previous.get(name) != version)
    if not previous:
        mode: ProcessingMode = "first_seen"
    elif changed:
        mode = "incremental_update"
    else:
        mode = "no_material_change"

    return {
        "source_versions": versions,
        "changed_sources": changed,
        "processing_mode": mode,
        "client_context": {
            "client": client or {},
            "as_of": state["as_of"],
            "changed_sources": changed,
        },
        "context_issues": issues,
        "status": "needs_confirmation" if issues else "context_ready",
        "trace": [f"context_agent:{mode}"],
    }


def route_context(
    state: ClientFlowState,
) -> Literal["wealth_intelligence_agent", "reuse_verified", "needs_confirmation"]:
    if state.get("context_issues"):
        return "needs_confirmation"
    if state.get("processing_mode") == "no_material_change" and state.get("meeting_brief"):
        return "reuse_verified"
    return "wealth_intelligence_agent"
