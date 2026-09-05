"""HTTP regressions for review readiness and connected-record evidence."""

import pytest
from fastapi.testclient import TestClient
from test_api import DATA, _analytics, _app, _verify, _wealth

from app.main import create_app
from app.pipeline.api_schemas import DemoViewModel
from app.pipeline.graph_adapter import AgentHooks


def test_readiness_requires_approval_of_current_version(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        initial = DemoViewModel.model_validate(client.get("/api/app").json())
        client_id = "CL-0003"
        base = {"client_id": client_id, "run_id": initial.run_id, "brief_version": 1}
        assert initial.clients[client_id].brief_status == "Needs review"
        for action, expected in [
            ("Approve", "Ready"),
            ("Reject", "Needs review"),
            ("Approve", "Ready"),
        ]:
            response = client.post("/api/reviews", json={**base, "action": action})
            assert response.status_code == 200, response.text
            view = DemoViewModel.model_validate(client.get("/api/app").json())
            assert view.clients[client_id].brief_status == expected
            assert view.clients["CL-0004"].brief_status == "Needs review"
        response = client.post(
            "/api/reviews",
            json={
                **base,
                "action": "Edit",
                "section": "summary",
                "text": "Discuss the recorded position carefully.",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["verification_report"]["passed"] is True
        view = DemoViewModel.model_validate(client.get("/api/app").json())
        assert view.clients[client_id].brief_version == 2
        assert view.clients[client_id].brief_status == "Needs review"
        response = client.post(
            "/api/reviews", json={**base, "brief_version": 2, "action": "Approve"}
        )
        assert response.status_code == 200, response.text
        assert client.get("/api/app").json()["clients"][client_id]["brief_status"] == "Ready"


@pytest.mark.parametrize("envelope", [False, True])
def test_cited_memory_card_resolves_persisted_connected_records(tmp_path, envelope):
    def context(state):
        record = {
            "id": "mail:" + state["client_id"],
            "client_id": state["client_id"],
            "source": "gmail",
            "occurred_at": "2026-08-20T00:00:00Z",
            "retrieved_at": "2026-08-26T00:00:00Z",
            "availability": "Cached",
            "provenance": "synthetic_fixture",
            "text": "Prefers a phone call.",
        }
        return {
            "context_issues": [],
            "connected_context": {
                "records": [record],
                "sources": {"gmail": "Cached"},
                "retrieval_log": [],
            }
            if envelope
            else [record],
            "memory_card": {
                "summary": {"text": "Prefers a phone call.", "citations": [record["id"]]}
            },
        }

    app = create_app(
        source_dir=DATA,
        curated_dir=tmp_path / "curated",
        database=tmp_path / "ledger.sqlite3",
        analytics=_analytics,
        agents=AgentHooks(context=context, wealth=_wealth, verifier=_verify),
    )
    with TestClient(app) as client:
        response = client.get("/api/app")
        assert response.status_code == 200, response.text
        view = DemoViewModel.model_validate(response.json())
        record_id = "mail:CL-0003"
        assert record_id not in view.evidence
        assert view.connected_evidence[record_id]["availability"] == "Cached"
        assert view.connected_evidence[record_id]["source"] == "gmail"
        assert view.connected_evidence[record_id]["text"] == "Prefers a phone call."
        memory_card = view.clients["CL-0003"].memory_card
        assert memory_card is not None
        summary = memory_card["summary"]
        assert isinstance(summary, dict)
        assert summary["citations"] == [record_id]
        assert view.evidence
