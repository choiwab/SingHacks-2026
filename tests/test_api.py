import asyncio
import json

import httpx

from app.main import app


def send(method: str, path: str, **kwargs) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(request())


def test_home_health_and_app_data_are_available() -> None:
    home = send("GET", "/")
    health = send("GET", "/api/health")
    data = send("GET", "/api/app")

    assert home.status_code == 200
    assert "Call these clients first" in home.text
    assert health.json() == {"status": "ok", "as_of": "2026-08-26"}
    assert data.status_code == 200
    assert len(data.json()["ranking"]) == 20


def test_review_is_the_only_live_write(tmp_path) -> None:
    review_log = tmp_path / "review_log.json"
    app.state.review_log_path = review_log

    response = send(
        "POST",
        "/api/reviews",
        json={
            "client_id": "CL-0003",
            "action": "Edit",
            "text": "Edited German opening.",
        },
    )

    assert response.status_code == 200
    saved = json.loads(review_log.read_text(encoding="utf-8"))
    assert saved[0]["action"] == "Edit"
    assert saved[0]["rm"] == "Priscilla Ong"
    assert saved[0]["text"] == "Edited German opening."


def test_review_rejects_unknown_client_and_action(tmp_path) -> None:
    app.state.review_log_path = tmp_path / "review_log.json"

    missing = send(
        "POST",
        "/api/reviews",
        json={"client_id": "CL-9999", "action": "Approve", "text": ""},
    )
    invalid = send(
        "POST",
        "/api/reviews",
        json={"client_id": "CL-0003", "action": "Send", "text": ""},
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
