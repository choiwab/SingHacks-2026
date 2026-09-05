"""Provider reads publish atomically into the same memory used by agents and MCP."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.runtime import persistent_data_flow
from app.mcp import external
from app.mcp.external_common import ConnectorSettings
from app.mcp.server import create_server
from app.mcp.service import load_memory
from app.mcp.store import MemoryStore

CUTOFF = datetime(2026, 8, 26, 23, 59, 59, 999999, tzinfo=UTC)
DATA = Path(__file__).resolve().parents[1] / "data"


def settings():
    return ConnectorSettings.model_validate(
        {
            "demo_accounts_only": True,
            "google_account_email": "rm@example.com",
            "microsoft_account_id": "00000000-0000-0000-0000-000000000001",
            "clients": {
                "CL-0003": {
                    "emails": ["client@example.com"],
                    "gmail": True,
                    "outlook_mail": True,
                    "google_calendar_ids": ["primary"],
                    "outlook_calendar_ids": ["demo-calendar"],
                }
            },
        }
    )


@pytest.fixture
def providers(monkeypatch):
    tokens = []

    def token(provider, _directory):
        tokens.append(provider)
        return "fake-token"

    def fetch(source):
        def read(ctx):
            return [
                ctx.record(
                    source=source,
                    native_id=source,
                    occurred_at=CUTOFF - timedelta(hours=1),
                    text="Client asks to discuss the tax funding plan. RM promised a summary.",
                    participants=ctx.scope.emails,
                    based_on=f"https://example.com/{ctx.provider}/{source}",
                )
            ]

        return read

    monkeypatch.setattr(external, "access_token", token)
    for name, source in (
        ("fetch_gmail", "gmail"),
        ("fetch_google_calendar", "calendar"),
        ("fetch_outlook_mail", "outlook"),
        ("fetch_outlook_calendar", "calendar"),
    ):
        monkeypatch.setattr(external, name, fetch(source))
    return tokens


def test_all_four_reads_are_live_then_durable_cached_and_citable(tmp_path, providers):
    store = MemoryStore(tmp_path / "records.sqlite3")
    live = external.read_connectors(settings(), store, "CL-0003", CUTOFF, tmp_path)
    assert len(live.records) == 4
    assert providers == ["google", "microsoft"]
    assert live.sources["outlook"] == "Live"
    assert live.sources["calendar"] == "Live"
    assert live.sources["teams"] == "Not connected"
    assert all(r.availability == "Live" for r in live.records)
    assert load_memory(DATA, store, "CL-0003", CUTOFF, connected=live).sources["gmail"] == "Live"
    restarted = MemoryStore(store.path)
    cached = load_memory(DATA, restarted, "CL-0003", CUTOFF)
    assert cached.sources["outlook"] == "Cached"
    assert all(r.availability == "Cached" for r in cached.records)
    with persistent_data_flow(DATA, tmp_path) as graph:
        result = graph.invoke(
            {
                "run_id": "connector-test",
                "client_id": "CL-0003",
                "as_of": "2026-08-26",
                "trace": [],
            },
            {"configurable": {"thread_id": "connector-test"}},
        )
    assert result["verification"]["passed"]
    assert result["status"] == "awaiting_review"
    assert "tax funding plan" in str(result["pack"]["memory_card"])


def test_failed_read_does_not_publish_partial_snapshot(tmp_path, providers, monkeypatch):
    store = MemoryStore(tmp_path / "records.sqlite3")
    original = external.read_connectors(settings(), store, "CL-0003", CUTOFF, tmp_path)

    def fail(_ctx):
        raise RuntimeError("secret provider error")

    monkeypatch.setattr(external, "fetch_gmail", lambda _ctx: [])
    monkeypatch.setattr(external, "fetch_outlook_mail", fail)
    with pytest.raises(OSError) as error:
        external.read_connectors(settings(), store, "CL-0003", CUTOFF, tmp_path)
    assert "secret" not in str(error.value)
    assert {r.id for r in store.context("CL-0003", CUTOFF).records} == {
        r.id for r in original.records
    }


def test_removed_records_leave_active_snapshot_but_keep_history(tmp_path, providers, monkeypatch):
    store = MemoryStore(tmp_path / "records.sqlite3")
    original = external.read_connectors(settings(), store, "CL-0003", CUTOFF, tmp_path)
    for name in (
        "fetch_gmail",
        "fetch_google_calendar",
        "fetch_outlook_mail",
        "fetch_outlook_calendar",
    ):
        monkeypatch.setattr(external, name, lambda _ctx: [])
    next_cutoff = CUTOFF + timedelta(days=1)
    external.read_connectors(settings(), store, "CL-0003", next_cutoff, tmp_path)
    assert store.context("CL-0003", next_cutoff).records == []
    assert store.context("CL-0003", next_cutoff).sources["outlook"] == "Cached"
    assert len(store.context("CL-0003", CUTOFF).records) == 4
    assert store.history("CL-0003", original.records[0].id)


def test_mcp_handler_uses_connectors_and_preserves_scope(tmp_path, providers):
    server = create_server(
        DATA, tmp_path / "records.sqlite3", {"CL-0003"}, connectors=settings(), token_dir=tmp_path
    )

    async def call():
        result = await server.call_tool(
            "get_client_context", {"client_id": "CL-0003", "as_of": CUTOFF.isoformat()}
        )
        assert "Live" in str(result)
        assert "outlook:microsoft:" in str(result)
        with pytest.raises(Exception, match="not enabled"):
            await server.call_tool(
                "get_client_context", {"client_id": "CL-0012", "as_of": CUTOFF.isoformat()}
            )

    asyncio.run(call())


def test_no_enabled_connectors_requires_no_oauth(tmp_path, providers):
    config = settings()
    config.clients["CL-0003"].gmail = False
    config.clients["CL-0003"].outlook_mail = False
    config.clients["CL-0003"].google_calendar_ids = []
    config.clients["CL-0003"].outlook_calendar_ids = []
    store = MemoryStore(tmp_path / "records.sqlite3")
    external.read_connectors(config, store, "CL-0003", CUTOFF, tmp_path)
    assert not providers


def test_configuration_requires_distinct_explicit_demo_identities():
    config = settings().model_dump()
    config["demo_accounts_only"] = False
    with pytest.raises(ValueError, match="demo-account"):
        ConnectorSettings.model_validate(config)
    config["demo_accounts_only"] = True
    config["google_account_email"] = "client@example.com"
    with pytest.raises(ValueError, match="distinct"):
        ConnectorSettings.model_validate(config)
