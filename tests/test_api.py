import asyncio
import json
from datetime import date
from pathlib import Path

import httpx

from app.main import create_app
from app.monday_brief import build_monday_brief

DATA = Path(__file__).resolve().parents[1] / "data"


def send(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def request() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(request())


def test_app_factory_has_no_build_or_write_side_effects(tmp_path) -> None:
    projection = build_monday_brief(DATA, as_of=date(2026, 8, 26))
    app = create_app(
        source_dir=tmp_path,
        database=":memory:",
        projection=projection,
        save_diagnostic=False,
    )

    assert not hasattr(app.state, "projection")
    assert list(tmp_path.iterdir()) == []


def test_home_health_and_typed_projection_are_available(tmp_path) -> None:
    projection = build_monday_brief(DATA, as_of=date(2026, 8, 26))
    app = create_app(
        source_dir=tmp_path,
        database=":memory:",
        projection=projection,
        save_diagnostic=False,
    )

    home = send(app, "GET", "/")
    health = send(app, "GET", "/api/health")
    data = send(app, "GET", "/api/monday-brief")
    old_endpoint = send(app, "GET", "/api/app")

    assert home.status_code == 200
    assert "Calls to make. Meetings to prepare." in home.text
    assert health.json() == {"status": "ok", "as_of": "2026-08-26"}
    assert data.status_code == 200
    assert data.json()["schema_version"] == 1
    assert len(data.json()["ranking"]) == 20
    assert old_endpoint.status_code == 404


def test_review_is_persisted_to_sqlite(tmp_path) -> None:
    projection = build_monday_brief(DATA, as_of=date(2026, 8, 26))
    database = tmp_path / "reviews.sqlite3"
    app = create_app(
        source_dir=tmp_path,
        database=database,
        projection=projection,
        save_diagnostic=False,
    )

    response = send(
        app,
        "POST",
        "/api/reviews",
        json={"client_id": "CL-0003", "action": "Edit", "text": "Edited German opening."},
    )

    assert response.status_code == 200
    assert response.json()["review"]["action"] == "Edit"
    assert response.json()["review"]["rm"] == "Priscilla Ong"
    assert response.json()["review"]["review_id"]
    assert database.exists()


def test_review_rejects_unknown_client_and_action(tmp_path) -> None:
    projection = build_monday_brief(DATA, as_of=date(2026, 8, 26))
    app = create_app(
        source_dir=tmp_path,
        database=":memory:",
        projection=projection,
        save_diagnostic=False,
    )

    missing = send(
        app,
        "POST",
        "/api/reviews",
        json={"client_id": "CL-9999", "action": "Approve", "text": ""},
    )
    invalid = send(
        app,
        "POST",
        "/api/reviews",
        json={"client_id": "CL-0003", "action": "Send", "text": ""},
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_legacy_log_is_imported_once_and_left_untouched(tmp_path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    legacy = generated / "review_log.json"
    legacy_payload = [
        {
            "client_id": "CL-0003",
            "action": "Approve",
            "text": "Original",
            "rm": "Priscilla Ong",
            "timestamp": "2026-08-26T01:00:00+00:00",
        }
    ]
    legacy.write_text(json.dumps(legacy_payload), encoding="utf-8")
    original = legacy.read_bytes()
    projection = build_monday_brief(DATA, as_of=date(2026, 8, 26))
    app = create_app(
        source_dir=tmp_path,
        database=generated / "reviews.sqlite3",
        projection=projection,
        save_diagnostic=False,
    )

    async def start_twice() -> None:
        async with app.router.lifespan_context(app):
            assert len(app.state.review_ledger.list()) == 1
        async with app.router.lifespan_context(app):
            assert len(app.state.review_ledger.list()) == 1

    asyncio.run(start_twice())
    assert legacy.read_bytes() == original
