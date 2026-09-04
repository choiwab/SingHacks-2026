from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline.features import legacy_analytics
from app.pipeline.graph_adapter import AgentHooks
from app.store import ReviewLedger

DATA = Path(__file__).resolve().parents[1] / "data"


def _analytics(sources, run_id):
    result = legacy_analytics(sources, run_id)
    result.context_issues = []
    return result


def _wealth(state):
    fact_id = state["fact_bundle"][0]["id"]
    return {
        "draft_brief": {
            "client_id": state["client_id"],
            "sections": {
                "summary": {"text": "Discuss the recorded position.", "citations": [fact_id]}
            },
        },
        "ranked_insights": [],
    }


def _verify(state):
    text = str(state.get("meeting_brief", {}))
    passed = "unsupported" not in text
    return {
        "verification_report": {"passed": passed, "errors": [] if passed else ["Unsupported claim"]}
    }


def _app(tmp_path, **kwargs):
    return create_app(
        source_dir=DATA,
        curated_dir=tmp_path / "curated",
        database=tmp_path / "reviews.sqlite3",
        analytics=_analytics,
        agents=AgentHooks(
            context=lambda state: {"context_issues": []}, wealth=_wealth, verifier=_verify
        ),
        **kwargs,
    )


def test_app_factory_has_no_read_or_write_side_effects(tmp_path):
    app = create_app(source_dir=tmp_path, database=tmp_path / "reviews.sqlite3")
    assert not hasattr(app.state, "pipeline_runtime")
    assert list(tmp_path.iterdir()) == []


def test_health_and_frontend_routes(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<main id='root'></main>")
    with TestClient(_app(tmp_path, frontend_dist=frontend)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "as_of": "2026-08-26"}
        assert client.get("/api/monday-brief").status_code == 404
        assert client.get("/api/unknown").status_code == 404
        assert "id='root'" in client.get("/clients/CL-0003").text


def test_app_is_read_only_and_edit_reverifies_new_version(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        initial = client.get("/api/app").json()
        assert len(initial["clients"]) == 20
        assert "selected" not in initial
        assert initial["calendar"] == []
        assert initial["data_health"] == "Current"
        ledger = cast(FastAPI, client.app).state.review_ledger
        before = len(ledger.list_briefs(initial["run_id"]))
        assert client.get("/api/app").json() == initial
        assert len(ledger.list_briefs(initial["run_id"])) == before
        body = {
            "client_id": "CL-0003",
            "run_id": initial["run_id"],
            "brief_version": 1,
            "action": "Edit",
            "section": "summary",
            "text": "unsupported replacement",
        }
        response = client.post("/api/reviews", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["brief_version"] == 2
        assert response.json()["verification_report"]["passed"] is False
        assert client.post("/api/reviews", json=body).status_code == 409
        approve = {key: body[key] for key in ("client_id", "run_id")}
        assert (
            client.post(
                "/api/reviews", json={**approve, "brief_version": 2, "action": "Approve"}
            ).status_code
            == 409
        )
        refreshed = client.get("/api/app").json()
        assert refreshed["data_health"] == "Needs confirmation"
        assert refreshed["clients"]["CL-0003"]["brief_version"] == 2
        assert refreshed["reviews"][0]["section"] == "summary"


def test_update_reset_retains_reviews_but_filters_by_run(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        seed = client.get("/api/app").json()
        updated = client.post("/api/demo/update", json={"action": "apply"})
        assert updated.status_code == 200, updated.text
        update = updated.json()
        assert update["run_id"] != seed["run_id"]
        assert update["data_health"] == "Updating"
        review = client.post(
            "/api/reviews",
            json={
                "run_id": update["run_id"],
                "client_id": "CL-0003",
                "brief_version": 1,
                "action": "Approve",
            },
        )
        assert review.status_code == 200, review.text
        assert len(client.get("/api/app").json()["reviews"]) == 1
        reset = client.post("/api/demo/update", json={"action": "reset"})
        assert reset.status_code == 200, reset.text
        after = client.get("/api/app").json()
        assert after["run_id"] == seed["run_id"]
        assert after["clients"] == seed["clients"]
        assert after["reviews"] == []
        assert len(cast(FastAPI, client.app).state.review_ledger.list(run_id=update["run_id"])) == 1
        stale = client.post(
            "/api/reviews",
            json={
                "run_id": update["run_id"],
                "client_id": "CL-0003",
                "brief_version": 1,
                "action": "Reject",
            },
        )
        assert stale.status_code == 409


def test_review_contract_rejects_unscoped_and_malformed_requests(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        view = client.get("/api/app").json()
        base = {"run_id": view["run_id"], "client_id": "CL-0003", "brief_version": 1}
        assert (
            client.post(
                "/api/reviews", json={"client_id": "CL-0003", "action": "Approve"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/reviews", json={**base, "action": "Edit", "text": "missing section"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/reviews", json={**base, "action": "Approve", "section": "summary"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/reviews", json={**base, "client_id": "CL-9999", "action": "Approve"}
            ).status_code
            == 404
        )
        assert client.post("/api/demo/update", json={"action": "unknown"}).status_code == 422


def test_restart_loads_persisted_briefs(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        initial = client.get("/api/app").json()
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/api/app").json() == initial
    ledger = ReviewLedger(tmp_path / "reviews.sqlite3")
    assert len(ledger.list_briefs(initial["run_id"])) == 20
    ledger.close()
