"""Shared local/MCP read boundary, preserving original dataset notes and durable additions."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from app.mcp.records import SOURCES, ConnectedContext
from app.mcp.store import MemoryStore
from app.pipeline.agent_inputs import load_dataset_notes


def load_memory(
    source_dir: Path,
    store: MemoryStore,
    client_id: str,
    as_of: datetime,
    revision: str = "current",
    *,
    connected: ConnectedContext | None = None,
) -> ConnectedContext:
    dataset = load_dataset_notes(source_dir, client_id, as_of, revision)
    saved = store.context(client_id, as_of)
    records = {record.id: record for record in dataset.records}
    for record in saved.records:
        if record.id in records:
            raise ValueError("Persistent additions cannot override original dataset notes")
        records[record.id] = record
    if connected:
        connected = ConnectedContext.model_validate(connected.model_dump())
        for record in connected.records:
            if record.client_id != client_id or record.occurred_at > as_of:
                raise ValueError("Connected records must match the client and As-of Date")
            if record.id in {r.id for r in dataset.records}:
                raise ValueError("Connected records cannot override original dataset notes")
            records[record.id] = record
    source_names: list[str] = [*SOURCES, *saved.sources]
    if connected:
        source_names.extend(connected.sources)
    sources: dict[str, Literal["Live", "Cached", "Not connected"]] = {
        source: "Live"
        if connected
        and connected.sources.get(source) == "Live"
        and all(r.availability == "Live" for r in records.values() if r.source == source)
        else "Cached"
        if any(r.source == source for r in records.values())
        else "Cached"
        if saved.sources.get(source) == "Cached"
        else dataset.sources.get(source, "Not connected")
        for source in dict.fromkeys(source_names)
    }
    for key, record in records.items():
        if sources[record.source] == "Cached":
            records[key] = record.model_copy(update={"availability": "Cached"})
    return ConnectedContext(
        records=sorted(records.values(), key=lambda record: (record.occurred_at, record.id)),
        sources=sources,
        retrieval_log=[
            *dataset.retrieval_log,
            *saved.retrieval_log,
            *(connected.retrieval_log if connected else []),
        ],
    )
