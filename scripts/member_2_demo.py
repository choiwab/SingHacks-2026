"""Offline integration example with a GOLDEN-FIXTURE verifier, not a production gate."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.agents.contracts import (
    CuratedClientBundle,
    MeetingPack,
    VerificationIssue,
    VerificationReport,
)
from app.agents.graph import build_agent_flow
from app.agents.state import AgentState
from app.mcp.connectors import replay_records
from app.mcp.records import ConnectedContext

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "member_2"


def load_bundle(client_id: str, as_of: date, revision: str) -> CuratedClientBundle:
    if revision not in {"initial", "updated", "memory_only", "financial_only"}:
        raise ValueError("Unknown demo revision")
    name = "updated" if revision in {"updated", "financial_only"} else "initial"
    bundle = CuratedClientBundle.model_validate_json(
        (FIXTURES / f"curated.{name}.json").read_text()
    )
    if bundle.client_id != client_id or bundle.as_of != as_of:
        raise ValueError("No curated fixture for that client/date")
    return bundle


def load_communications(client_id: str, as_of: datetime, revision: str) -> ConnectedContext:
    name = "updated" if revision in {"updated", "memory_only"} else "initial"
    return replay_records(
        FIXTURES / f"communications.{name}.json", client_id=client_id, as_of=as_of
    )


def fixture_verifier(
    pack: MeetingPack,
    bundle: CuratedClientBundle,
    connected: ConnectedContext,
) -> VerificationReport:
    """Only admit frozen test claims. Member 4 must replace this in real integration."""
    allowed: set[tuple[str, str, tuple[str, ...]]] = set()
    for path in sorted(FIXTURES.glob("golden.*.json")):
        expected = MeetingPack.model_validate_json(path.read_text())
        allowed.update((c.id, c.text, tuple(c.citations)) for c in expected.claims())
    issues = []
    for claim in pack.claims():
        permitted_edit = (
            claim.authorship == "rm"
            and claim.id == "opening"
            and claim.text == ("Could we start by discussing your priorities for this meeting?")
        )
        if (claim.id, claim.text, tuple(claim.citations)) not in allowed and not permitted_edit:
            issues.append(VerificationIssue(claim_id=claim.id, reason="Not a frozen demo claim"))
    return VerificationReport(pack_version=pack.version, passed=not issues, issues=issues)


def demo_input(revision: str = "initial") -> AgentState:
    return {
        "run_id": f"demo-{revision}",
        "client_id": "CL-0003",
        "as_of": "2026-08-26",
        "revision": revision,
        "trace": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update", action="store_true", help="Approve the initial fixture, then update"
    )
    parser.add_argument(
        "--live", action="store_true", help="Opt in to OpenAI (requires external env)"
    )
    args = parser.parse_args()
    graph = build_agent_flow(
        load_bundle=load_bundle,
        load_communications=load_communications,
        verify_pack=fixture_verifier,
        live_generation=args.live,
    )
    config: RunnableConfig = {"configurable": {"thread_id": "member-2-demo"}}
    result = graph.invoke(demo_input(), config=config)
    if args.update and result.get("__interrupt__"):
        graph.invoke(
            Command(
                resume={
                    "client_id": "CL-0003",
                    "pack_version": result["pack_version"],
                    "action": "Approve",
                }
            ),
            config=config,
        )
        result = graph.invoke(demo_input("updated"), config=config)
    output: dict[str, Any] = dict(cast(dict[str, Any], result))
    output.pop("__interrupt__", None)
    output["verifier_kind"] = "golden_fixture_only"
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
