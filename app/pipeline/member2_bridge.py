"""Opt-in offline Member 2 generation over immutable Member 3 artifacts.

This connects generation and candidate edits. It does not supply financial Signals or a
passing evidence gate. Communication loaders must return complete pinned snapshots.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime, time
from typing import Any, cast

from app.agents.briefing import rm_briefing_agent
from app.agents.context import CommunicationLoader, context_agent
from app.agents.contracts import CuratedClientBundle, MeetingPack, Signal, fingerprint
from app.agents.state import AgentState
from app.agents.verification import verify_meeting_pack
from app.agents.wealth import wealth_intelligence_agent
from app.analytics.signals import build_signals
from app.mcp.records import SOURCES, CommunicationRecord, ConnectedContext
from app.pipeline.agent_inputs import note_topics
from app.pipeline.generation_state import ClientFlowState
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.schemas import Fact as ArtifactFact
from app.pipeline.schemas import Signal as ArtifactSignal


def disconnected(client_id: str, as_of: datetime, revision: str) -> ConnectedContext:
    """Explicit absence of connectors, with no synthetic messages added."""
    return ConnectedContext(
        records=[], sources={source: "Not connected" for source in SOURCES}, retrieval_log=[]
    )


def pinned_notes(store: ArtifactStore) -> CommunicationLoader:
    """Read RM notes from the pinned run, so an overlay update is not served stale notes.

    ``agent_inputs.load_dataset_notes`` reads ``data/`` directly and cannot see the overlay
    the runtime applies, so the same normalization is done over the published bundle instead.
    """

    def load(client_id: str, as_of: datetime, revision: str) -> ConnectedContext:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Dataset notes require an aware as-of timestamp")
        records = []
        for note in store.load_curated_bundle(client_id, run_id=revision).rm_notes:
            occurred_at = datetime.combine(note.note_date, time.min, tzinfo=UTC)
            if occurred_at > as_of:
                continue
            payload = note.model_dump(mode="json")
            records.append(
                CommunicationRecord.model_validate(
                    {
                        "id": f"notes:{note.note_id}",
                        "client_id": client_id,
                        "source": "notes",
                        "version": fingerprint(payload),
                        "occurred_at": occurred_at,
                        "retrieved_at": as_of,
                        "participants": [note.rm_name],
                        "text": note.note,
                        "topics": note_topics(note.note),
                        "provenance": "dataset",
                        "availability": "Cached",
                        "based_on": [f"data/rm_notes.json:{note.note_id}"],
                    }
                )
            )
        records.sort(key=lambda item: (item.occurred_at, item.id))
        return ConnectedContext(
            records=records,
            sources={
                source: "Cached" if source == "notes" and records else "Not connected"
                for source in SOURCES
            },
            retrieval_log=[
                {
                    "source": "notes",
                    "mode": "pinned_artifact_read",
                    "client_id": client_id,
                    "as_of": as_of.isoformat(),
                    "record_ids": [record.id for record in records],
                    "date_precision": "day (UTC midnight convention)",
                }
            ],
        )

    return load


def project_pack(pack: MeetingPack) -> dict[str, Any]:
    """Derive all presentation copies and identity from the authoritative pack."""
    content = pack.model_dump(mode="json")
    return {
        "pack": content,
        "pack_version": pack.version,
        "meeting_brief": {"sections": deepcopy(content["brief"])},
        "insights": deepcopy(content["insights"]),
        "memory_card": deepcopy(content["memory_card"]),
        "information_requests": deepcopy(content["information_requests"]),
    }


def edit_pack(body: dict[str, Any], claim_id: str, text: str) -> dict[str, Any]:
    """Apply M2's opening/talking-point edit rules to a persisted candidate copy."""
    pack = MeetingPack.model_validate(body.get("pack"))
    if body.get("pack_version") != pack.version:
        raise ValueError("Stored meeting pack version does not match its content")
    if not text.strip() or len(text) > 2000:
        raise ValueError("Edited text must contain 1 to 2000 characters")
    editable = {claim.id: claim for claim in [pack.brief.opening, *pack.brief.talking_points]}
    if claim_id not in editable:
        raise KeyError("Only the opening and talking point claim IDs may be edited")
    editable[claim_id].text = text
    editable[claim_id].authorship = "rm"
    return {**deepcopy(body), **project_pack(pack)}


def derive_signals(client_id: str, facts: list[ArtifactFact]) -> list[Signal]:
    """Regroup pinned one-number Facts into M4's Signal groups.

    ``legacy_analytics`` publishes empty Signal Sets, so the scorer's groups are rebuilt
    here from the same pinned artifacts rather than reopening raw sources. Each Fact keeps
    the engine's complete ``inputs``, which is the legacy ``numbers`` dict the scorer reads.
    """
    legacy: dict[str, dict[str, Any]] = {}
    members: dict[str, list[str]] = {}
    for fact in facts:
        legacy_id = fact.id.rsplit(":", 1)[0]
        legacy.setdefault(
            legacy_id,
            {
                "id": legacy_id,
                "numbers": fact.inputs,
                "source_rows": list(fact.evidence_ids),
                "event_ids": [],
                "confidence": "high" if fact.confidence >= 1.0 else "medium",
            },
        )
        members.setdefault(legacy_id, []).append(fact.id)
    keys = {legacy_id.rsplit(":", 1)[-1] for legacy_id in legacy}
    if not {"profile", "mandate-gap", "deadline", "concentration"} <= keys:
        # The scorer indexes these groups directly; an incomplete client yields no Signals.
        return []
    signals = []
    for signal in build_signals(client_id, list(legacy.values())):
        expanded = [member for original in signal["fact_ids"] for member in members[original]]
        signals.append(Signal.model_validate({**signal, "fact_ids": expanded}))
    return signals


def member2_hooks(
    store: ArtifactStore,
    *,
    load_communications: CommunicationLoader | None = None,
    signal_adapter: Callable[[ArtifactSignal], Signal] | None = None,
) -> AgentHooks:
    """Build generation hooks; a supplied adapter owns the finalized Signal wording mapping.

    Existing nonempty Signals require an explicit adapter because the canonical schema
    does not define Member 2 topic/uncertainty strings or integral score conversion.
    """

    load_communications = load_communications or pinned_notes(store)

    def bundle(client: str, as_of: date, revision: str) -> CuratedClientBundle:
        facts = store.load_fact_bundle(client, run_id=revision)
        signals = store.load_signal_set(client, run_id=revision)
        if signals.signals and signal_adapter is None:
            raise ValueError("Finalized Member 4 Signal mapping is not connected")
        mapped = (
            [Signal.model_validate(signal_adapter(s)) for s in signals.signals]
            if signal_adapter is not None
            else derive_signals(client, facts.facts)
        )
        evidence = store.load_evidence_map(run_id=revision)
        quality = store.load_data_quality_report(run_id=revision, client_id=client)
        return CuratedClientBundle(
            client_id=client,
            as_of=as_of,
            version=revision,
            facts=facts.facts,
            signals=mapped,
            evidence={
                key: entry
                for key, entry in evidence.entries.items()
                if entry.record.get("client_id") in (None, client)
            },
            fact_descriptions=facts.descriptions,
            quality_issues=[f.message for f in quality.findings if f.severity == "error"],
        )

    def generate(initial: ClientFlowState) -> dict[str, Any]:
        client_id, run_id = initial["client_id"], initial["run_id"]

        def load_bundle(client: str, as_of: date, revision: str) -> CuratedClientBundle:
            if (client, revision) != (client_id, run_id):
                raise ValueError("Generation must use the pinned client and run")
            # Generation and verification must rederive from identical content,
            # so both sides share the one pinned bundle builder above.
            return bundle(client, as_of, revision)

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
            **project_pack(MeetingPack.model_validate(pack)),
            "trace": state.get("trace", []),
            "memory_index": state.get("memory_index"),
            "section_versions": state.get("section_versions"),
            "input_versions": state.get("input_versions"),
            "connected_context": context.get("records", []),
            "connected_sources": context.get("sources", {}),
            "retrieval_log": context.get("retrieval_log", []),
            "context_issues": list(initial.get("context_issues", [])),
        }

    def verify(state: ClientFlowState) -> dict[str, Any]:
        """Run M4's evidence gate over the pack the generator actually persisted."""
        pack = MeetingPack.model_validate(state.get("pack") or {})
        as_of = date.fromisoformat(state["as_of"])
        connected = ConnectedContext(
            records=cast(Any, state.get("connected_context") or []),
            sources=cast(
                Any,
                state.get("connected_sources")
                or disconnected("", datetime.combine(as_of, time.min, tzinfo=UTC), "").sources,
            ),
            retrieval_log=cast(Any, state.get("retrieval_log") or []),
        )
        report = verify_meeting_pack(
            pack, bundle(state["client_id"], as_of, state["run_id"]), connected
        )
        return {
            "verification_report": {
                "passed": report.passed,
                "errors": [f"{issue.claim_id}: {issue.reason}" for issue in report.issues],
                "as_of": state["as_of"],
                "pack_version": report.pack_version,
                "verification_scope": "meeting_pack",
            },
            "status": "verified" if report.passed else "needs_confirmation",
            "trace": [f"verify_meeting_pack:{'pass' if report.passed else 'fail'}"],
        }

    return AgentHooks(generator=generate, edit=edit_pack, verifier=verify)
