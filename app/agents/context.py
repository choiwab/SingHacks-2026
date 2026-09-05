"""Assemble curated data and communication context through the supplied loaders."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time
from typing import Any

from app.agents.contracts import CuratedClientBundle, fingerprint
from app.agents.state import AgentState
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import MemoryIndex
from app.pipeline.errors import SourceValidationError

BundleLoader = Callable[[str, date, str], CuratedClientBundle]
CommunicationLoader = Callable[[str, datetime, str], ConnectedContext]


def context_agent(
    state: AgentState,
    *,
    load_bundle: BundleLoader,
    load_communications: CommunicationLoader,
    generation_policy: str,
) -> dict[str, Any]:
    prior_pack = state.get("pack")
    if prior_pack and prior_pack.get("client_id") and prior_pack["client_id"] != state["client_id"]:
        # A checkpoint/thread is bound to one client. Reject before any retrieval or review.
        raise ValueError("Use a separate graph thread for each client")
    try:
        if prior_pack and not prior_pack.get("client_id"):
            raise ValueError("Stored pack has no Client identity")
        as_of = date.fromisoformat(state["as_of"])
        cutoff = datetime.combine(as_of, time.max, UTC)
        client_id = state["client_id"]
        revision = state.get("revision", "initial")
        loaded = load_bundle(client_id, as_of, revision)
        bundle = CuratedClientBundle.model_validate(
            loaded.model_dump(mode="json") if isinstance(loaded, CuratedClientBundle) else loaded
        )
        if bundle.client_id != client_id or bundle.as_of != as_of:
            raise ValueError("Curated bundle client/date mismatch")
        if bundle.quality_issues:
            return {
                "context_failed": True,
                "issues": bundle.quality_issues,
                "status": "needs_confirmation",
                "trace": [{"node": "context", "result": "data_quality_failure"}],
            }
        loaded_context = load_communications(client_id, cutoff, bundle.pipeline_run_id or revision)
        connected = ConnectedContext.model_validate(
            loaded_context.model_dump(mode="json")
            if isinstance(loaded_context, ConnectedContext)
            else loaded_context
        )
        # Scope before exposing records to any agent, even for a custom connector callback.
        if any(r.client_id != client_id or r.occurred_at > cutoff for r in connected.records):
            raise ValueError("Communication loader returned out-of-scope records")
        snapshot = state.get("memory_index")
        index = (
            MemoryIndex.restore(snapshot)
            if snapshot and snapshot["client_id"] == client_id
            else MemoryIndex(client_id=client_id, as_of=cutoff)
        )
        index.as_of = cutoff
        changed_records = index.update(connected.records)
        versions = {
            "bundle": bundle.content_version(),
            "memory": index.version,
            "availability": fingerprint(connected.sources),
            "generation": generation_policy,
        }
        same_client = not prior_pack or prior_pack["client_id"] == client_id
        previous = state.get("input_versions", {}) if same_client else {}
        financial_change = versions["bundle"] != previous.get("bundle")
        memory_change = any(versions[k] != previous.get(k) for k in ("memory", "availability"))
        prior_bundle = state.get("bundle", {})
        observed_changes = {}
        for field in ("facts", "signals"):
            old_items = {item["id"]: item for item in prior_bundle.get(field, [])}
            new_items = {item.id: item.model_dump(mode="json") for item in getattr(bundle, field)}
            observed_changes[field] = sorted(
                key
                for key in old_items.keys() | new_items.keys()
                if old_items.get(key) != new_items.get(key)
            )
        mode = (
            "first_seen"
            if not previous
            else "no_material_change"
            if versions == previous and not state.get("context_failed")
            else "incremental_update"
        )
        change_kind = (
            "combined"
            if financial_change and memory_change
            else "financial"
            if financial_change
            else "memory"
            if memory_change
            else "none"
        )
        return {
            "context_failed": False,
            "bundle": bundle.model_dump(mode="json"),
            "connected_context": connected.model_dump(mode="json"),
            "memory_index": index.snapshot(),
            "input_versions": versions,
            "changed_records": changed_records,
            "processing_mode": mode,
            "change_kind": change_kind,
            "prior_status": state.get("status", "new"),
            "last_approved": state.get("last_approved") if same_client else None,
            "history": state.get("history", []) if same_client else [],
            "issues": state.get("issues", []) if mode == "no_material_change" else [],
            "review": None,
            "status": "context_ready",
            "trace": [
                {
                    "node": "context",
                    "result": mode,
                    "change_kind": change_kind,
                    "changed_record_ids": changed_records,
                    "observed_changes": observed_changes,
                    "input_versions": versions,
                    "data_change_report": bundle.change_report.model_dump(mode="json"),
                    "retrievals": connected.retrieval_log,
                }
            ],
        }
    except SourceValidationError as exc:
        return {
            "context_failed": True,
            "issues": [str(item) for item in exc.diagnostics],
            "status": "needs_confirmation",
            "trace": [{"node": "context", "result": "source_validation_failed"}],
        }
    except (ValueError, OSError) as exc:
        # Validation errors may contain entire records: don't echo them into the public trace.
        return {
            "context_failed": True,
            "issues": [f"Context unavailable or invalid ({type(exc).__name__})"],
            "status": "needs_confirmation",
            "trace": [{"node": "context", "result": "failed"}],
        }


def route_context(state: AgentState) -> str:
    if state.get("issues"):
        return "needs_confirmation"
    if state.get("processing_mode") == "no_material_change" and state.get("pack"):
        return "reuse"
    return "wealth"
