"""Offline memory contracts and startup hydration use isolated persistence."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.mcp.seed import seed_demo_memory
from app.mcp.store import MemoryStore

DATA = Path(__file__).resolve().parents[1] / "data"
FIXTURE = DATA / "fixtures/connected/records.json"


def test_demo_seed_is_idempotent_and_scoped(tmp_path):
    store = MemoryStore(tmp_path / "memory/records.sqlite3")
    assert seed_demo_memory(store, FIXTURE) == 18
    assert seed_demo_memory(store, FIXTURE) == 0
    cutoff = datetime(2026, 8, 26, tzinfo=UTC)
    for number in range(1, 7):
        client_id = f"CL-{number:04d}"
        records = store.context(client_id, cutoff).records
        assert len(records) == 3
        assert all(
            r.client_id == client_id and r.provenance == "synthetic_fixture" for r in records
        )
        assert all(r.availability == "Cached" and r.retrieved_at <= cutoff for r in records)
        assert sum(r.source == "calendar" and r.scheduled_at is not None for r in records) == 1
        assert all(len(store.history(client_id, r.id)) == 1 for r in records)
    assert seed_demo_memory(store, tmp_path / "missing.json") == 0


def test_memory_endpoints_and_ranking_survive_restart(tmp_path):
    for iteration in range(3):
        with TestClient(
            create_app(
                source_dir=DATA,
                curated_dir=tmp_path / "curated",
                database=tmp_path / "reviews.sqlite3",
                memory_dir=tmp_path / "memory",
            )
        ) as client:
            response = client.get("/api/clients/CL-0003/memory")
            assert response.status_code == 200
            memory = response.json()
            assert set(memory) == {"client_id", "as_of", "records", "sources", "retrieval_log"}
            assert memory["client_id"] == "CL-0003"
            assert memory["sources"] == {
                "gmail": "Cached",
                "calendar": "Cached",
                "notes": "Cached",
                "teams": "Not connected",
                "outlook": "Not connected",
            }
            assert {r["source"] for r in memory["records"]} == {"notes", "gmail", "calendar"}
            assert all(r["client_id"] == "CL-0003" for r in memory["records"])
            assert client.get("/api/clients/CL-9999/memory").status_code == 404
            assert client.get("/api/communications?source=invalid").status_code == 422
            all_records = client.get("/api/communications").json()["records"]
            dates = [
                datetime.fromisoformat(r["scheduled_at"] or r["occurred_at"]) for r in all_records
            ]
            assert dates == sorted(dates, reverse=True)
            for source, count in [("gmail", 12), ("calendar", 6), ("outlook", 0)]:
                result = client.get(f"/api/communications?source={source}")
                assert result.status_code == 200
                records = result.json()["records"]
                assert len(records) == count
                assert all(r["source"] == source and r["client_name"] for r in records)
            view = client.get("/api/app").json()
            assert view["data_health"] == "Current"
            assert view["clients"]["CL-0003"]["brief_version"] == (1 if iteration == 0 else 2)
            assert view["clients"]["CL-0002"]["brief_version"] == 1
            assert len(view["calendar"]) == 6
            assert len(view["ranking"]) == 20
            assert [r["score"] for r in view["ranking"]] == sorted(
                [r["score"] for r in view["ranking"]], reverse=True
            )
            assert sum(r["meeting"] is not None for r in view["ranking"]) == 6
            assert all(
                r["reason"] and r["urgency"] in {"now", "soon", "watch"} for r in view["ranking"]
            )
            assert client.get("/api/app").json() == view
            reset = client.post("/api/demo/update", json={"action": "reset"})
            assert reset.status_code == 200
            assert reset.json()["ranking"] == view["ranking"]

        if iteration == 0:
            store = MemoryStore(tmp_path / "memory/records.sqlite3")
            record = store.history("CL-0003", "gmail:demo-cl-0003-1")[0]
            store.put(
                record.model_copy(
                    update={
                        "version": "2",
                        "text": record.text + "\nPlease allow time for questions at our meeting.",
                    }
                )
            )
