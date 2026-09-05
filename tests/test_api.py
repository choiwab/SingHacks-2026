import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.main import create_app
from app.pipeline.schemas import ReviewRequest
from app.store import ReviewLedger

DATA = Path(__file__).resolve().parents[1] / "data"


def send(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def request() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(request())


def test_app_factory_has_no_read_or_write_side_effects(tmp_path) -> None:
    app = create_app(source_dir=tmp_path, database=tmp_path / "reviews.sqlite3")

    assert not hasattr(app.state, "client_ids")
    assert not hasattr(app.state, "review_ledger")
    assert list(tmp_path.iterdir()) == []


def test_health_reports_as_of_and_old_projection_route_is_gone(tmp_path) -> None:
    app = create_app(source_dir=DATA, database=":memory:")

    health = send(app, "GET", "/api/health")
    projection = send(app, "GET", "/api/monday-brief")

    assert health.json() == {"status": "ok", "as_of": "2026-08-26"}
    assert projection.status_code == 404


def test_frontend_serves_index_and_falls_back_for_client_routes(tmp_path) -> None:
    frontend = tmp_path / "frontend"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text("<main id='root'></main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ready')", encoding="utf-8")
    app = create_app(source_dir=DATA, database=":memory:", frontend_dist=frontend)

    home = send(app, "GET", "/")
    route = send(app, "GET", "/clients/CL-0003")
    asset = send(app, "GET", "/assets/app.js")
    unknown_api = send(app, "GET", "/api/unknown")

    assert home.status_code == 200
    assert "id='root'" in home.text
    assert route.status_code == 200
    assert "id='root'" in route.text
    assert asset.status_code == 200
    assert "ready" in asset.text
    assert unknown_api.status_code == 404


def test_review_is_persisted_to_sqlite(tmp_path) -> None:
    database = tmp_path / "reviews.sqlite3"
    app = create_app(source_dir=DATA, database=database)

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
    stored = {record.review_id: record for record in ReviewLedger(database).list()}
    assert stored[response.json()["review"]["review_id"]].client_id == "CL-0003"


def test_review_rejects_unknown_client_and_action(tmp_path) -> None:
    app = create_app(source_dir=DATA, database=":memory:")

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


def test_review_ledger_accepts_concurrent_writes(tmp_path) -> None:
    ledger = ReviewLedger(tmp_path / "reviews.sqlite3")
    request = ReviewRequest(client_id="CL-0003", action="Edit", text="Reviewed")

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: ledger.append(request, rm="Priscilla Ong"), range(12)))

    assert len({record.review_id for record in records}) == 12
    assert len(ledger.list()) == 12


def test_legacy_import_is_transactional_and_idempotent(tmp_path) -> None:
    source = tmp_path / "review_log.json"
    source.write_text(
        json.dumps(
            [
                {
                    "client_id": "CL-0003",
                    "action": "Approve",
                    "text": "Looks good",
                    "rm": "Priscilla Ong",
                    "timestamp": "2026-08-26T01:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    ledger = ReviewLedger(":memory:")

    assert ledger.import_legacy_json(source) == 1
    assert ledger.import_legacy_json(source) == 0
    assert len(ledger.list()) == 1
    assert source.exists()
    ledger.close()
