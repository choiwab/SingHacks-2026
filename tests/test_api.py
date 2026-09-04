import asyncio

import httpx

from app.main import app


def send_request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_home_and_health_are_available() -> None:
    home = send_request("GET", "/")
    health = send_request("GET", "/api/health")

    assert home.status_code == 200
    assert "Prepare Lau's meeting" in home.text
    assert health.json() == {"status": "ok", "as_of": "2026-08-26"}


def test_prepare_returns_grounded_scenario_and_parallel_council() -> None:
    response = send_request("POST", "/api/prepare")
    payload = response.json()

    assert response.status_code == 200
    assert payload["scenario"]["stressed"]["ltv_pct"] == 73.94
    assert len(payload["council"]) == 5
    assert all(specialist["evidence_ids"] for specialist in payload["council"])
    assert payload["action_plan"]["status"] == "Draft for RM review"


def test_rehearsal_rejects_unknown_choices() -> None:
    response = send_request("POST", "/api/rehearse", json={"opening": "sell everything"})

    assert response.status_code == 422


def test_approval_requires_acknowledgement() -> None:
    approval_request = {
        "acknowledged": False,
        "tasks": [
            {
                "id": "TASK-01",
                "title": "Confirm external liquidity",
                "owner": "Priscilla Ong",
                "due": "2026-09-05",
                "system": "CRM task",
            }
        ],
    }

    response = send_request("POST", "/api/action-plan/approve", json=approval_request)

    assert response.status_code == 422
    assert "acknowledge" in response.json()["detail"]


def test_approval_returns_previews_without_external_writes() -> None:
    approval_request = {
        "acknowledged": True,
        "tasks": [
            {
                "id": "TASK-01",
                "title": "Confirm external liquidity",
                "owner": "Priscilla Ong",
                "due": "2026-09-05",
                "system": "CRM task",
            }
        ],
    }

    response = send_request("POST", "/api/action-plan/approve", json=approval_request)
    payload = response.json()

    assert response.status_code == 200
    assert payload["writes_executed"] == 0
    assert payload["status"] == "Approved for preview only"
    assert payload["outcome"]["revenue"] is None
