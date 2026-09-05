"""Opt-in offline Member 2 generation over immutable Member 3 artifacts.

This connects generation only. It does not supply missing financial Signals or a
passing evidence gate. Communication loaders must return complete pinned snapshots.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any, cast

from app.agents.briefing import rm_briefing_agent
from app.agents.context import CommunicationLoader, context_agent
from app.agents.contracts import CuratedClientBundle, Signal
from app.agents.state import AgentState
from app.agents.wealth import wealth_intelligence_agent
from app.mcp.records import SOURCES, ConnectedContext
from app.pipeline.generation_state import ClientFlowState
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.schemas import Signal as ArtifactSignal


def disconnected(client_id: str, as_of: datetime, revision: str) -> ConnectedContext:
    """Explicit absence of connectors, with no synthetic messages added."""
    return ConnectedContext(
        records=[], sources={source: "Not connected" for source in SOURCES}, retrieval_log=[]
    )


def member2_hooks(
    store: ArtifactStore,
    *,
    load_communications: CommunicationLoader = disconnected,
    signal_adapter: Callable[[ArtifactSignal], Signal] | None = None,
) -> AgentHooks:
    """Build generation hooks; a supplied adapter owns the finalized Signal wording mapping.

    Existing nonempty Signals require an explicit adapter because the canonical schema
    does not define Member 2 topic/uncertainty strings or integral score conversion.
    """

    def generate(initial: ClientFlowState) -> dict[str, Any]:
        client_id, run_id = initial["client_id"], initial["run_id"]

        def load_bundle(client: str, as_of: date, revision: str) -> CuratedClientBundle:
            if (client, revision) != (client_id, run_id):
                raise ValueError("Generation must use the pinned client and run")
            facts = store.load_fact_bundle(client, run_id=revision)
            signals = store.load_signal_set(client, run_id=revision)
            if signals.signals and signal_adapter is None:
                raise ValueError("Finalized Member 4 Signal mapping is not connected")
            mapped = (
                [Signal.model_validate(signal_adapter(s)) for s in signals.signals]
                if signal_adapter is not None
                else []
            )
            evidence = store.load_evidence_map(run_id=revision)
            quality = store.load_data_quality_report(run_id=revision, client_id=client)
            return CuratedClientBundle(
                client_id=client,
                as_of=as_of,
                version=revision,
                facts=facts.facts,
                signals=mapped,
                evidence=evidence.entries,
                quality_issues=[f.message for f in quality.findings if f.severity == "error"],
            )

        state: AgentState = {
            "run_id": run_id,
            "client_id": client_id,
            "as_of": initial["as_of"],
            "revision": run_id,
            "trace": [],
        }

        def apply(update: dict[str, Any]) -> None:
            trace = [*state.get("trace", []), *update.get("trace", [])]
            state.update(cast(AgentState, update))
            state["trace"] = trace

        apply(
            context_agent(
                state,
                load_bundle=load_bundle,
                load_communications=load_communications,
                generation_policy="v1:deterministic",
            )
        )
        if state.get("context_failed"):
            return {
                "meeting_brief": {},
                "insights": [],
                "memory_card": None,
                "connected_context": [],
                "trace": state.get("trace", []),
                "context_issues": [*initial.get("context_issues", []), *state.get("issues", [])],
            }
        apply(wealth_intelligence_agent(state))
        apply(rm_briefing_agent(state, live=False))
        pack = state.get("pack") or {}
        context = state.get("connected_context", {})
        return {
            "meeting_brief": {"sections": pack["brief"]},
            "insights": pack["insights"],
            "memory_card": pack["memory_card"],
            "pack": pack,
            "pack_version": state.get("pack_version"),
            "trace": state.get("trace", []),
            "memory_index": state.get("memory_index"),
            "section_versions": state.get("section_versions"),
            "input_versions": state.get("input_versions"),
            "connected_context": context.get("records", []),
            "connected_sources": context.get("sources", {}),
            "retrieval_log": context.get("retrieval_log", []),
            "context_issues": list(initial.get("context_issues", [])),
        }

    return AgentHooks(generator=generate)
