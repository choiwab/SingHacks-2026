"""Real data-directory execution, verification failures, and human-review lifecycle."""

import json
import shutil
import socket
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.agents.contracts import MeetingPack
from app.agents.state import AgentState
from app.agents.verification import verify_meeting_pack
from app.agents.wording import ALTERNATE_OPENING
from app.pipeline.agent_inputs import load_curated_bundle, load_dataset_notes
from scripts.run_client_flow import build_data_flow

DATA = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 8, 26)
INPUT: AgentState = {
    "run_id": "real-data",
    "client_id": "CL-0003",
    "as_of": str(AS_OF),
    "trace": [],
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The dataset sample must run offline")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


def decision(result, action="Approve", **kwargs):
    return Command(
        resume={
            "client_id": "CL-0003",
            "pack_version": result["pack_version"],
            "action": action,
            **kwargs,
        }
    )


def test_actual_sources_reach_review_with_discrepancy_and_temporal_evidence():
    result = build_data_flow(DATA).invoke(INPUT, {"configurable": {"thread_id": "real"}})
    assert result["status"] == "awaiting_review"
    assert result["__interrupt__"]
    assert result["verification"]["passed"]
    assert [item["node"] for item in result["trace"]] == ["context", "wealth", "briefing", "verify"]
    insights = result["pack"]["insights"]
    suitability = next(item for item in insights if item["signal_id"].endswith(":suitability"))
    assert "71.5% against a 30% maximum" in suitability["why_it_matters"]["text"]
    assert "not make any changes" in suitability["why_it_matters"]["text"]
    assert "not investment returns" in str(result["pack"]["brief"]["uncertainty"])
    assert "Event-log association" in str(result["pack"]["brief"]["uncertainty"])
    assert all(
        record["provenance"] == "dataset" for record in result["connected_context"]["records"]
    )


def test_real_data_review_edit_approval_reuse_and_updates(tmp_path):
    source = tmp_path / "data"
    shutil.copytree(DATA, source, ignore=shutil.ignore_patterns("generated"))
    events = {}
    graph = build_data_flow(
        source, record_review=lambda event: events.update({event["event_id"]: event})
    )
    config: RunnableConfig = {"configurable": {"thread_id": "lifecycle"}}
    initial = graph.invoke(INPUT, config)
    edited = graph.invoke(decision(initial, "Edit", changes={"opening": ALTERNATE_OPENING}), config)
    assert edited["status"] == "awaiting_review"
    assert edited["pack_version"] != initial["pack_version"]
    approved = graph.invoke(decision(edited), config)
    assert approved["status"] == "approved"
    unchanged = graph.invoke(INPUT, config)
    assert unchanged["status"] == "approved"
    assert unchanged["trace"][-1]["node"] == "reuse"
    assert unchanged["pack_version"] == approved["pack_version"]
    notes_path = source / "rm_notes.json"
    notes = json.loads(notes_path.read_text())
    notes.append(
        {
            **next(n for n in notes if n["note_id"] == "N-006"),
            "note_id": "N-029",
            "note_date": "2026-08-25",
            "note": "Client asks to discuss the tax funding plan at the next meeting.",
        }
    )
    notes_path.write_text(json.dumps(notes))
    memory = graph.invoke(INPUT, config)
    assert memory["change_kind"] == "memory"
    assert memory["bundle"] == initial["bundle"]
    assert memory["last_approved"] == approved["pack"]
    assert memory["status"] == "awaiting_review"
    holdings_path = source / "holdings.csv"
    holdings = pd.read_csv(holdings_path)
    selected = (holdings.client_id == "CL-0003") & (holdings.snapshot_date == str(AS_OF))
    holdings.loc[selected, "market_value_base"] *= 1.01
    holdings.to_csv(holdings_path, index=False)
    changed = graph.invoke(INPUT, config)
    assert changed["change_kind"] == "financial"
    assert changed["pack_version"] != memory["pack_version"]
    assert changed["status"] == "awaiting_review"
    assert changed["trace"][-4]["observed_changes"]["facts"]
    assert {event["action"] for event in events.values()} == {"Edit", "Approve"}


@pytest.mark.parametrize("mutation", ["fact", "memory", "score", "citations", "uncertainty"])
def test_real_gate_rejects_unsupported_or_missing_claims(mutation):
    result = build_data_flow(DATA).invoke(INPUT, {"configurable": {"thread_id": "gate"}})
    pack = MeetingPack.model_validate(result["pack"])
    if mutation == "fact":
        pack.insights[0].facts[0].text = "Guaranteed return of 500%."
    elif mutation == "memory":
        pack.memory_card.recent_updates.claims[0].text = "Client approved selling everything."
    elif mutation == "score":
        pack.insights[0].score = 1
    elif mutation == "citations":
        pack.brief.opening.citations = ["notes:other-client#fake"]
    else:
        pack.brief.uncertainty = []
    bundle = load_curated_bundle(DATA, "CL-0003", AS_OF)
    notes = load_dataset_notes(DATA, "CL-0003", datetime(2026, 8, 26, 23, 59, tzinfo=UTC))
    report = verify_meeting_pack(pack, bundle, notes)
    assert not report.passed
    assert report.issues


def test_invalid_sources_stop_with_actionable_diagnostics(tmp_path):
    result = build_data_flow(tmp_path).invoke(INPUT, {"configurable": {"thread_id": "missing"}})
    assert result["status"] == "needs_confirmation"
    assert "clients.csv" in " ".join(result["issues"])
    assert not result.get("__interrupt__")
