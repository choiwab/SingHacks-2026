from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.client_flow import SOURCE_FILES, ClientFlowState, build_client_flow

DATA = Path(__file__).resolve().parents[1] / "data"


def _input(**updates: Any) -> ClientFlowState:
    state = {
        "run_id": "run-margarethe",
        "client_id": "CL-0003",
        "source_dir": str(DATA),
        "as_of": "2026-08-26",
        "trace": [],
    }
    return cast(ClientFlowState, state | updates)


def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


def test_first_seen_flow_rechecks_an_edit_then_approves() -> None:
    graph = build_client_flow()
    config = _config("first-seen")

    paused = graph.invoke(_input(), config=config)

    assert paused["processing_mode"] == "first_seen"
    assert paused["verification_report"]["passed"] is True
    assert paused["__interrupt__"][0].value["kind"] == "rm_review"
    assert paused["trace"] == [
        "context_agent:first_seen",
        "wealth_intelligence_agent:complete",
        "rm_briefing_agent:complete",
        "evidence_gate:pass",
    ]

    edited = graph.invoke(
        Command(
            resume={
                "client_id": "CL-0003",
                "action": "Edit",
                "text": "Reviewed opening",
            }
        ),
        config=config,
    )

    assert edited["meeting_brief"]["opening"]["text"] == "Reviewed opening"
    assert edited["trace"][-2:] == ["human_review:edit", "evidence_gate:pass"]
    assert edited["__interrupt__"][0].value["kind"] == "rm_review"

    completed = graph.invoke(
        Command(resume={"client_id": "CL-0003", "action": "Approve", "text": ""}),
        config=config,
    )

    assert completed["status"] == "approved"
    assert completed["dashboard_view_model"]["meeting_brief"]["client_id"] == "CL-0003"
    assert completed["trace"][-2:] == ["human_review:approve", "finalize:approved"]


def test_unknown_client_stops_before_intelligence() -> None:
    graph = build_client_flow()

    result = graph.invoke(
        _input(client_id="CL-9999"),
        config=_config("missing-client"),
    )

    assert result["status"] == "needs_confirmation"
    assert any("CL-9999 does not exist" in issue for issue in result["context_issues"])
    assert "wealth_intelligence_agent:complete" not in result["trace"]


def test_unchanged_sources_reuse_prior_verified_brief() -> None:
    versions = {name: sha256((DATA / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    previous_brief = {"client_id": "CL-0003", "opening": {"text": "Already reviewed"}}
    graph = build_client_flow()

    result = graph.invoke(
        _input(previous_source_versions=versions, meeting_brief=previous_brief),
        config=_config("unchanged"),
    )

    assert result["processing_mode"] == "no_material_change"
    assert result["status"] == "unchanged"
    assert result["dashboard_view_model"]["meeting_brief"] == previous_brief
    assert result["trace"] == [
        "context_agent:no_material_change",
        "reuse_verified:complete",
    ]
