"""Actual MCP initialization and tool calls over loopback Streamable HTTP."""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.agents.contracts import CuratedClientBundle
from app.mcp.records import ConnectedContext


class MCPClient:
    def __init__(self, url: str):
        target = urlsplit(url)
        if (
            target.scheme != "http"
            or target.hostname != "127.0.0.1"
            or target.username
            or target.password
            or target.query
            or target.fragment
            or target.path != "/mcp"
        ):
            raise ValueError("Demo MCP URL must be http://127.0.0.1:PORT/mcp")
        self.url = url

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # ponytail: one session per call suits the demo; pool sessions if latency matters.
        async with (
            asyncio.timeout(30),
            httpx.AsyncClient(
                timeout=20,
                follow_redirects=False,
                trust_env=False,
            ) as http,
            streamable_http_client(self.url, http_client=http) as (read, write, _),
            ClientSession(read, write, read_timeout_seconds=timedelta(seconds=20)) as session,
        ):
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError or result.structuredContent is None:
                raise ValueError("MCP tool failed or returned no structured content")
            return result.structuredContent

    def _call(
        self, name: str, client_id: str, as_of: date | datetime, revision: str = "current"
    ) -> dict[str, Any]:
        try:
            return asyncio.run(
                self.call(
                    name,
                    {
                        "client_id": client_id,
                        "as_of": as_of.isoformat(),
                        "revision": revision,
                    },
                )
            )
        except Exception as exc:
            # Do not leak server errors, source text, or transport internals into public traces.
            raise OSError("MCP unavailable or invalid response") from exc

    def bundle(self, client_id: str, as_of: date, revision: str = "current") -> CuratedClientBundle:
        return CuratedClientBundle.model_validate(
            self._call("get_client_bundle", client_id, as_of, revision)
        )

    def context(
        self, client_id: str, as_of: datetime, revision: str = "current"
    ) -> ConnectedContext:
        connected = ConnectedContext.model_validate(
            self._call("get_client_context", client_id, as_of, revision)
        )
        connected.retrieval_log.append(
            {
                "mode": "mcp_streamable_http",
                "transport": "Live",
                "client_id": client_id,
                "as_of": as_of.isoformat(),
                "record_ids": [record.id for record in connected.records],
            }
        )
        return connected
