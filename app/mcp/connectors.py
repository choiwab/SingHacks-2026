"""Offline replay of explicitly authored, read-only demo records."""

from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from app.mcp.records import SOURCES, CommunicationRecord, ConnectedContext


def replay_records(path: Path, *, client_id: str, as_of: datetime) -> ConnectedContext:
    """A missing source is visible, never represented as a successful live query."""
    if as_of.tzinfo is None:
        raise ValueError("Replay requires an aware as-of timestamp")
    try:
        records = TypeAdapter(list[CommunicationRecord]).validate_json(path.read_text())
    except FileNotFoundError:
        records = []
    selected: dict[str, CommunicationRecord] = {}
    for record in records:
        if record.client_id != client_id or record.occurred_at > as_of:
            continue
        cached = record.model_copy(update={"availability": "Cached"})
        if record.id in selected and selected[record.id] != cached:
            raise ValueError(f"Conflicting duplicate record: {record.id}")
        selected[record.id] = cached
    ordered = sorted(selected.values(), key=lambda r: (r.occurred_at, r.id))
    return ConnectedContext(
        records=ordered,
        sources={
            source: "Cached" if any(r.source == source for r in ordered) else "Not connected"
            for source in SOURCES
        },
        retrieval_log=[
            {
                "source": source,
                "mode": "fixture_replay",
                "client_id": client_id,
                "as_of": as_of.isoformat(),
                "record_ids": [r.id for r in ordered if r.source == source],
            }
            for source in SOURCES
        ],
    )
