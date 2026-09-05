"""Opt-in external reads, normalized into the context used by the offline agent flow."""

from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.mcp.external_common import ConnectorSettings, ReadContext
from app.mcp.google_connectors import fetch_gmail, fetch_google_calendar
from app.mcp.microsoft_connectors import fetch_outlook_calendar, fetch_outlook_mail
from app.mcp.oauth import access_token
from app.mcp.records import SOURCES, ConnectedContext
from app.mcp.store import MemoryStore


def read_connectors(
    settings: ConnectorSettings,
    store: MemoryStore,
    client_id: str,
    as_of: datetime,
    token_dir: Path,
    *,
    transport: httpx.BaseTransport | None = None,
) -> ConnectedContext:
    if client_id not in settings.clients:
        raise ValueError("Client is not enabled for external connectors")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("External reads require an aware As-of Date")
    scope = settings.clients[client_id]
    sources: dict[str, str] = dict.fromkeys(SOURCES, "Not connected")
    if scope.outlook_mail:
        sources["outlook"] = "Not connected"
    records = []
    log = []
    retrieved_at = datetime.now(UTC)
    try:
        with httpx.Client(
            timeout=15, follow_redirects=False, trust_env=False, transport=transport
        ) as http:
            tokens = {}
            for provider, source, enabled, fetch in (
                ("google", "gmail", scope.gmail, fetch_gmail),
                ("google", "calendar", bool(scope.google_calendar_ids), fetch_google_calendar),
                ("microsoft", "outlook", scope.outlook_mail, fetch_outlook_mail),
                ("microsoft", "calendar", bool(scope.outlook_calendar_ids), fetch_outlook_calendar),
            ):
                if not enabled:
                    continue
                if provider not in tokens:
                    tokens[provider] = access_token(provider, token_dir)
                batch = fetch(
                    ReadContext(
                        settings,
                        client_id,
                        scope,
                        as_of,
                        retrieved_at,
                        http,
                        tokens[provider],
                        provider,
                    )
                )
                if any(
                    r.client_id != client_id
                    or r.source != source
                    or r.occurred_at > as_of
                    or r.provenance != "recorded_live"
                    or r.availability != "Live"
                    for r in batch
                ):
                    raise ValueError("Connector returned invalid records")
                records.extend(batch)
                sources[source] = "Live"
                log.append(
                    {
                        "mode": "provider_read",
                        "source": source,
                        "provider": provider,
                        "client_id": client_id,
                        "as_of": as_of.isoformat(),
                        "retrieved_at": retrieved_at.isoformat(),
                        "record_ids": [r.id for r in batch],
                    }
                )
        unique = {r.id: r for r in records}
        if len(unique) != len(records):
            raise ValueError("Duplicate provider record IDs")
        context = ConnectedContext.model_validate(
            {"records": records, "sources": sources, "retrieval_log": log}
        )
        store.save_connector_snapshot(client_id, as_of, context)
        return context
    except Exception:
        # No provider bodies, messages, tokens, or OAuth errors in graph/MCP output.
        # Offline replay is explicit; a failed live read never silently grants approval.
        raise OSError(
            "External connector unavailable or invalid. Check account setup, scopes, and bounds."
        ) from None
