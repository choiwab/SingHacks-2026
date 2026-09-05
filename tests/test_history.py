from fastapi.testclient import TestClient
from test_api import _app


def test_client_history_exposes_versions_prior_run_and_operational_trace(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        seed = client.get("/api/app").json()["run_id"]
        initial = client.get("/api/clients/CL-0003/history")
        assert initial.status_code == 200
        history = initial.json()
        assert history["run_id"] == seed
        assert len(history["versions"]) == 1
        assert history["versions"][0]["trace"]
        assert history["versions"][0]["meeting_brief"]["sections"]["summary"]
        edit = client.post(
            "/api/reviews",
            json={
                "run_id": seed,
                "client_id": "CL-0003",
                "brief_version": 1,
                "action": "Edit",
                "section": "summary",
                "text": "unsupported",
            },
        )
        assert edit.status_code == 200
        versions = client.get("/api/clients/CL-0003/history").json()["versions"]
        assert [version["brief_version"] for version in versions] == [2, 1]
        assert versions[0]["meeting_brief"] is None
        assert versions[1]["meeting_brief"] is not None
        updated = client.post("/api/demo/update", json={"action": "apply"}).json()["run_id"]
        history = client.get("/api/clients/CL-0003/history").json()
        assert history["run_id"] == updated
        assert [(v["run_id"], v["brief_version"]) for v in history["versions"]] == [
            (updated, 1),
            (seed, 2),
            (seed, 1),
        ]
        client.post("/api/demo/update", json={"action": "reset"})
        reset_history = client.get("/api/clients/CL-0003/history").json()
        assert all(v["run_id"] == seed for v in reset_history["versions"])
        assert client.get("/api/clients/CL-9999/history").status_code == 404
        assert client.get("/api/clients/CL-0003/history?run_id=invalid").status_code == 422
