"""Test-only browser server with real persistence and injected deterministic agents.

Run with ``uvicorn --app-dir tests browser_app:create_browser_app --factory``.
Never import this factory from app.main or use it as the product demo server. The
verifier below is a deliberately limited test double, not the production Evidence Gate.
Each process owns a temporary ledger and artifacts, leaving data/generated untouched.
"""

from copy import deepcopy
from datetime import UTC, datetime
from tempfile import TemporaryDirectory
from typing import Any

from app.main import create_app
from app.pipeline.features import legacy_analytics
from app.pipeline.graph_adapter import AgentHooks


def _analytics(sources, run_id):
    result = legacy_analytics(sources, run_id)
    result.context_issues = []  # Explicit test dependency, not a production readiness override.
    return result


def _claim(identifier: str, text: str, citations: list[str], kind: str = "suggestion"):
    return {"id": identifier, "text": text, "citations": citations, "kind": kind}


def _generate(state):
    client_id = state["client_id"]
    notes = state["client_context"]["rm_notes"]
    latest = max(notes, key=lambda note: (note["note_date"], note["note_id"])) if notes else None
    facts = state["fact_bundle"]
    reference = facts[0]["id"]
    records = []
    if latest:
        record_id = f"notes:{latest['note_id']}"
        records.append(
            {
                "id": record_id,
                "client_id": client_id,
                "source": "notes",
                "version": state["run_id"],
                "occurred_at": f"{latest['note_date']}T00:00:00Z",
                "retrieved_at": f"{state['as_of']}T00:00:00Z",
                "participants": [latest["rm_name"]],
                "text": latest["note"],
                "topics": ["recent_updates"],
                "provenance": "dataset",
                "availability": "Cached",
            }
        )
        reference = record_id
    if client_id == "CL-0003":
        records.append(
            {
                "id": "calendar:browser-test-meeting",
                "client_id": client_id,
                "source": "calendar",
                "version": "browser-test-v1",
                "occurred_at": "2026-08-24T09:00:00Z",
                "scheduled_at": "2026-08-31T02:30:00Z",
                "retrieved_at": "2026-08-26T00:00:00Z",
                "participants": ["Priscilla Ong", "Margarethe Voss-Brenner"],
                "text": "Synthetic browser test meeting: review the funding question.",
                "topics": ["meeting"],
                "provenance": "synthetic_fixture",
                "availability": "Cached",
            }
        )
    changed = state["processing_mode"] == "incremental_update"
    opening = (
        "Could we review the earlier payment date together?"
        if changed
        else "Could we review your planned payment together?"
    )
    sections = {
        "summary": [_claim("summary", "Prepare the recorded client conversation.", [reference])],
        "opening": _claim("opening", opening, [reference]),
        "talking_points": [
            _claim("topic-funding", "Review the planned funding need.", [reference])
        ],
        "questions": [
            _claim("question-funding", "Which funding sources should we review?", [reference])
        ],
        "uncertainty": [
            _claim("uncertainty", "Funding availability needs confirmation.", [reference])
        ],
    }
    memory: dict[str, Any] = {
        name: {"claims": [], "evidence_gap": "Not recorded in this test input."}
        for name in (
            "who_they_are",
            "personality_and_style",
            "stated_needs_and_goals",
            "recent_updates",
            "open_promises",
            "advice_notes",
        )
    }
    if latest:
        memory["recent_updates"] = {
            "claims": [_claim("last-note", latest["note"], [reference], "memory")]
        }
    return {
        "meeting_brief": {"sections": sections},
        "memory_card": memory,
        "connected_context": records,
        "insights": [],
        "context_issues": [],
        "trace": ["test-only browser generator"],
    }


def _verify(state):
    passed = "unsupported" not in str(state.get("meeting_brief", {})).lower()
    return {
        "verification_report": {
            "passed": passed,
            "errors": [] if passed else ["Test verifier rejected unsupported wording"],
            "verification_scope": "test_double_only",
        }
    }


def _edit(body, claim_id, text):
    result = deepcopy(body)
    sections = result["meeting_brief"]["sections"]
    editable = [sections["opening"], *sections["talking_points"]]
    for claim in editable:
        if claim["id"] == claim_id:
            claim["text"] = text
            claim["authorship"] = "rm"
            return result
    raise KeyError("Only opening and talking points are editable")


def create_browser_app():
    temporary = TemporaryDirectory(prefix="singhacks-browser-test-")
    from pathlib import Path

    root = Path(temporary.name)
    application = create_app(
        curated_dir=root / "curated",
        database=root / "reviews.sqlite3",
        analytics=_analytics,
        agents=AgentHooks(generator=_generate, verifier=_verify, edit=_edit),
    )
    application.state.browser_test_directory = temporary
    application.state.browser_test_started = datetime.now(UTC)
    return application
