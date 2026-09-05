"""Real MCP transports and durable graph restarts, without external accounts or models."""

import asyncio
import json
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agents.runtime import persistent_data_flow
from app.agents.state import AgentState
from app.mcp.client import MCPClient
from app.mcp.records import CommunicationRecord
from app.mcp.store import MemoryStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INPUT: AgentState = {
    "run_id": "persistent-demo",
    "client_id": "CL-0003",
    "as_of": "2026-08-26",
    "trace": [],
}
CONFIG: RunnableConfig = {"configurable": {"thread_id": "sample:CL-0003"}}


def interaction():
    return CommunicationRecord(
        id="notes:demo-meeting",
        client_id="CL-0003",
        source="notes",
        version="1",
        occurred_at=datetime(2026, 8, 26, 10, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 26, 10, tzinfo=UTC),
        participants=["Demo Relationship Manager"],
        text="Client asks to discuss the tax funding plan. RM promised a follow-up summary.",
        topics=["recent_updates", "stated_needs_and_goals", "open_promises"],
        provenance="synthetic_fixture",
    )


def test_restart_preserves_review_and_memory_updates(tmp_path):
    with persistent_data_flow(DATA, tmp_path) as graph:
        first = graph.invoke(INPUT, CONFIG)
        assert first["processing_mode"] == "first_seen"
        assert first["verification"]["passed"]
    with persistent_data_flow(DATA, tmp_path) as graph:
        assert graph.get_state(CONFIG).next == ("human_review",)
        approved = graph.invoke(
            Command(
                resume={
                    "client_id": "CL-0003",
                    "pack_version": first["pack_version"],
                    "action": "Approve",
                }
            ),
            CONFIG,
        )
        assert approved["status"] == "approved"
    with persistent_data_flow(DATA, tmp_path) as graph:
        unchanged = graph.invoke(INPUT, CONFIG)
        assert unchanged["processing_mode"] == "no_material_change"
        assert unchanged["status"] == "approved"
    MemoryStore(tmp_path / "records.sqlite3").put(interaction())
    with persistent_data_flow(DATA, tmp_path) as graph:
        updated = graph.invoke(INPUT, CONFIG)
        assert updated["change_kind"] == "memory"
        assert updated["status"] == "awaiting_review"
        assert updated["pack_version"] != first["pack_version"]
        assert updated["last_approved"] == approved["pack"]
        assert "notes:demo-meeting" in updated["changed_records"]
        assert "tax funding plan" in str(updated["pack"]["memory_card"])


def test_stdio_tools_are_real_read_only_and_scoped(tmp_path):
    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "app.mcp.server",
                "--source-dir",
                str(DATA),
                "--memory-dir",
                str(tmp_path),
            ],
            cwd=str(ROOT),
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            assert {tool.name for tool in tools} == {
                "get_client_bundle",
                "get_client_context",
                "search_client_memory",
            }
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
            result = await session.call_tool(
                "search_client_memory",
                {
                    "client_id": "CL-0003",
                    "as_of": "2026-08-26T23:59:59Z",
                    "query": "tax",
                },
            )
            assert not result.isError
            assert result.structuredContent is not None
            assert result.structuredContent["matches"]
            denied = await session.call_tool(
                "get_client_context",
                {
                    "client_id": "CL-0012",
                    "as_of": "2026-08-26T23:59:59Z",
                },
            )
            assert denied.isError
            invalid = await session.call_tool(
                "get_client_context",
                {
                    "client_id": "CL-0003",
                    "as_of": "2026-08-26T12:00:00",
                },
            )
            assert invalid.isError

    asyncio.run(exercise())


def test_direct_resume_rechecks_durable_inputs(tmp_path):
    with persistent_data_flow(DATA, tmp_path) as graph:
        first = graph.invoke(INPUT, CONFIG)
    MemoryStore(tmp_path / "records.sqlite3").put(interaction())
    with persistent_data_flow(DATA, tmp_path) as graph:
        refreshed = graph.invoke(
            Command(
                resume={
                    "client_id": "CL-0003",
                    "pack_version": first["pack_version"],
                    "action": "Approve",
                }
            ),
            CONFIG,
        )
        assert refreshed["status"] == "awaiting_review"
        assert refreshed["pack_version"] != first["pack_version"]
        assert not refreshed.get("review_events")
        assert "notes:demo-meeting" in refreshed["changed_records"]
    assert (tmp_path / "checkpoints.sqlite3").stat().st_mode & 0o077 == 0


def test_http_mcp_supplies_graph_inputs_and_fails_closed(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [
        sys.executable,
        "-m",
        "app.mcp.server",
        "--transport",
        "streamable-http",
        "--port",
        str(port),
        "--source-dir",
        str(DATA),
        "--memory-dir",
        str(tmp_path),
    ]
    with (tmp_path / "server.log").open("w") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    pytest.fail((tmp_path / "server.log").read_text())
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        pytest.fail("MCP server startup timed out")
                    time.sleep(0.05)
            url = f"http://127.0.0.1:{port}/mcp"
            with persistent_data_flow(DATA, tmp_path, mcp_url=url) as graph:
                first = graph.invoke(INPUT, CONFIG)
                assert first["status"] == "awaiting_review", first.get("issues")
                assert first["verification"]["passed"]
                assert first["connected_context"]["retrieval_log"][-1]["transport"] == "Live"
                assert first["connected_context"]["sources"]["gmail"] == "Not connected"
                assert all(
                    r["availability"] == "Cached" for r in first["connected_context"]["records"]
                )
            MemoryStore(tmp_path / "records.sqlite3").put(interaction())
            with persistent_data_flow(DATA, tmp_path, mcp_url=url) as graph:
                updated = graph.invoke(INPUT, CONFIG)
                assert updated["change_kind"] == "memory"
                assert updated["verification"]["passed"]
                assert "notes:demo-meeting" in updated["changed_records"]
        finally:
            process.terminate()
            process.wait(timeout=10)
    with persistent_data_flow(DATA, tmp_path, mcp_url=url) as graph:
        failed = graph.invoke(INPUT, CONFIG)
        assert failed["status"] == "needs_confirmation"
        assert failed["context_failed"]


def test_cli_refuses_stale_review_after_new_interaction(tmp_path):
    with persistent_data_flow(DATA, tmp_path) as graph:
        first = graph.invoke(INPUT, CONFIG)
    decision = tmp_path / "review.json"
    decision.write_text(
        json.dumps(
            {"client_id": "CL-0003", "pack_version": first["pack_version"], "action": "Approve"}
        )
    )
    MemoryStore(tmp_path / "records.sqlite3").put(interaction())
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_client_flow",
            "--memory-dir",
            str(tmp_path),
            "--review-file",
            str(decision),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 2
    assert "stale" in process.stderr
    with persistent_data_flow(DATA, tmp_path) as graph:
        assert graph.get_state(CONFIG).values["status"] == "awaiting_review"


@pytest.mark.parametrize(
    "url",
    ["https://example.com/mcp", "http://127.0.0.1.evil/mcp", "http://user:pass@127.0.0.1/mcp"],
)
def test_mcp_client_cannot_send_client_data_to_remote_hosts(url):
    with pytest.raises(ValueError):
        MCPClient(url)
