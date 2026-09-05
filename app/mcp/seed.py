"""Idempotent import of explicitly synthetic demo communications."""

import json
from pathlib import Path

from app.mcp.records import CommunicationRecord
from app.mcp.store import MemoryStore


def seed_demo_memory(store: MemoryStore, fixture: Path) -> int:
    if not fixture.is_file():
        return 0
    records = [CommunicationRecord.model_validate(item) for item in json.loads(fixture.read_text())]
    inserted = 0
    for record in records:
        if any(
            item.version == record.version for item in store.history(record.client_id, record.id)
        ):
            continue
        store.put(record)
        inserted += 1
    return inserted
