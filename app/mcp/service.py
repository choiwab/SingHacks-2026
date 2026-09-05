"""Shared local/MCP read boundary, preserving original dataset notes and durable additions."""

from datetime import datetime
from pathlib import Path

from app.mcp.records import SOURCES, ConnectedContext
from app.mcp.store import MemoryStore
from app.pipeline.agent_inputs import load_dataset_notes


def load_memory(
    source_dir: Path,
    store: MemoryStore,
    client_id: str,
    as_of: datetime,
    revision: str = "current",
) -> ConnectedContext:
    dataset = load_dataset_notes(source_dir, client_id, as_of, revision)
    saved = store.context(client_id, as_of)
    records = {record.id: record for record in dataset.records}
    for record in saved.records:
        if record.id in records:
            raise ValueError("Persistent additions cannot override original dataset notes")
        records[record.id] = record
    return ConnectedContext(
        records=sorted(records.values(), key=lambda record: (record.occurred_at, record.id)),
        sources={
            source: "Cached"
            if any(r.source == source for r in records.values())
            else dataset.sources[source]
            for source in SOURCES
        },
        retrieval_log=[*dataset.retrieval_log, *saved.retrieval_log],
    )
