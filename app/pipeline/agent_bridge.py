"""Wire the existing LangGraph agents and strict gate to immutable pipeline artifacts."""

from datetime import UTC, date, datetime, time
from functools import partial
from typing import Any

from app.agents.context import CommunicationLoader
from app.agents.contracts import MeetingPack
from app.agents.graph import build_agent_flow
from app.agents.verification import verify_meeting_pack
from app.agents.versioning import generation_policy_version
from app.mcp.records import ConnectedContext
from app.mcp.retrieval import record_content
from app.pipeline.agent_inputs import load_pinned_notes
from app.pipeline.agent_projection import project_agent_bundle
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.member2_bridge import edit_pack, project_pack


def phase_a_hooks(
    store: ArtifactStore, *, load_communications: CommunicationLoader | None = None
) -> AgentHooks:
    """Use dataset notes by default; callers may supply complete read-only connected snapshots."""
    communications = load_communications or partial(load_pinned_notes, store)

    def load_bundle(client_id: str, as_of: date, run_id: str):
        bundle = project_agent_bundle(store, client_id, run_id)
        if bundle.as_of != as_of:
            raise ValueError("Agent inputs must match the pinned As-of Date")
        return bundle

    def generate(initial) -> dict[str, Any]:
        client_id, run_id = initial["client_id"], initial["run_id"]
        graph = build_agent_flow(
            load_bundle=load_bundle,
            load_communications=communications,
            verify_pack=verify_meeting_pack,
            generation_policy=generation_policy_version(),
        )
        result = graph.invoke(
            {
                "run_id": run_id,
                "client_id": client_id,
                "as_of": initial["as_of"],
                "revision": run_id,
                "trace": [],
            },
            {"configurable": {"thread_id": f"{run_id}:{client_id}"}},
        )
        context = result.get("connected_context", {})
        body = {
            "trace": result.get("trace", []),
            "memory_index": result.get("memory_index"),
            "section_versions": result.get("section_versions"),
            "input_versions": result.get("input_versions"),
            "connected_context": context.get("records", []),
            "connected_sources": context.get("sources", {}),
            "retrieval_log": context.get("retrieval_log", []),
            "context_issues": [*initial.get("context_issues", []), *result.get("issues", [])],
        }
        if not result.get("pack"):
            return {**body, "meeting_brief": {}, "insights": [], "memory_card": None}
        return {**body, **project_pack(MeetingPack.model_validate(result["pack"]))}

    def verify(initial) -> dict[str, Any]:
        reasons = []
        pack_version = initial.get("pack_version")
        try:
            pack = MeetingPack.model_validate(initial.get("pack"))
            if pack.version != pack_version:
                raise ValueError("Stored pack version differs from its content")
            projected = project_pack(pack)
            for key in ("meeting_brief", "memory_card", "information_requests"):
                if initial.get(key) != projected[key]:
                    raise ValueError("Presentation differs from its authoritative meeting pack")
            if initial.get("ranked_insights") != projected["insights"]:
                raise ValueError("Insight projection differs from its authoritative meeting pack")
            bundle = load_bundle(
                initial["client_id"], date.fromisoformat(initial["as_of"]), initial["run_id"]
            )
            connected = ConnectedContext(
                records=initial.get("connected_context", []),
                sources=initial.get("connected_sources", {}),
                retrieval_log=initial.get("retrieval_log", []),
            )
            current = communications(
                initial["client_id"],
                datetime.combine(bundle.as_of, time.max, UTC),
                initial["run_id"],
            )
            if {record.id: record_content(record) for record in current.records} != {
                record.id: record_content(record) for record in connected.records
            } or current.sources != connected.sources:
                raise ValueError("Connected Records changed; refresh before review")
            if pack.input_versions.get("generation") != generation_policy_version():
                raise ValueError("Generation policy changed; refresh before review")
            report = verify_meeting_pack(pack, bundle, connected)
            reasons = [f"{issue.claim_id}: {issue.reason}" for issue in report.issues]
        except (ValueError, OSError, KeyError, TypeError):
            reasons = [
                "Pinned inputs, meeting pack or connected context are unavailable or invalid"
            ]
        return {
            "status": "awaiting_review" if not reasons else "needs_confirmation",
            "verification_report": {
                "passed": not reasons,
                "errors": reasons,
                "pack_version": pack_version,
                "verification_scope": "source_backed_constrained_wording",
            },
        }

    return AgentHooks(generator=generate, verifier=verify, edit=edit_pack)
