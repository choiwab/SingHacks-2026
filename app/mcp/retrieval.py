"""Small deterministic TF-IDF index, scoped to one client and as-of timestamp."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.agents.contracts import fingerprint
from app.mcp.records import CommunicationRecord


def record_content(record: CommunicationRecord) -> dict[str, Any]:
    return record.model_dump(
        mode="json", exclude={"retrieved_at", "availability"}, exclude_none=True
    )


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold())


class MemoryIndex:
    def __init__(self, *, client_id: str, as_of: datetime):
        if as_of.tzinfo is None:
            raise ValueError("Index requires an aware timestamp")
        self.client_id = client_id
        self.as_of = as_of
        self.chunks: dict[str, dict[str, Any]] = {}
        self.record_versions: dict[str, str] = {}

    def update(self, records: list[CommunicationRecord]) -> list[str]:
        eligible: dict[str, CommunicationRecord] = {}
        for record in records:
            if record.client_id != self.client_id or record.occurred_at > self.as_of:
                continue
            if record.id in eligible and record != eligible[record.id]:
                raise ValueError(f"Conflicting duplicate record: {record.id}")
            eligible[record.id] = record
        versions = {key: fingerprint(record_content(r)) for key, r in eligible.items()}
        changed = sorted(
            key
            for key in self.record_versions.keys() | versions.keys()
            if self.record_versions.get(key) != versions.get(key)
        )
        self.chunks = {
            key: value for key, value in self.chunks.items() if value["record_id"] not in changed
        }
        for key in changed:
            if key not in eligible:
                continue
            record = eligible[key]
            # ponytail: bounded text spans suit demo messages; token chunking for long documents.
            for match in re.finditer(r"[^\n]{1,1000}", record.text):
                chunk_id = f"{key}#{versions[key][:12]}:{match.start()}-{match.end()}"
                self.chunks[chunk_id] = {
                    "id": chunk_id,
                    "record_id": key,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(),
                    "topics": record.topics,
                    "occurred_at": record.occurred_at.isoformat(),
                }
        self.record_versions = versions
        return changed

    @property
    def version(self) -> str:
        return fingerprint(self.record_versions)

    def search(self, query: str, *, topic: str, limit: int = 3) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        chunks = list(self.chunks.values())
        counts = [Counter(tokens(chunk["text"])) for chunk in chunks]
        frequency = Counter(word for count in counts for word in count)
        idf = {word: math.log((1 + len(chunks)) / (1 + n)) + 1 for word, n in frequency.items()}
        query_vector = {word: n * idf.get(word, 1) for word, n in Counter(tokens(query)).items()}
        query_norm = math.sqrt(sum(n * n for n in query_vector.values()))
        results = []
        for chunk, count in zip(chunks, counts, strict=True):
            if topic != "recent_updates" and topic not in chunk["topics"]:
                continue
            vector = {word: n * idf[word] for word, n in count.items()}
            norm = math.sqrt(sum(n * n for n in vector.values()))
            score = (
                (
                    sum(value * query_vector.get(word, 0) for word, value in vector.items())
                    / (norm * query_norm)
                )
                if norm and query_norm
                else 0
            )
            results.append({**chunk, "score": round(score, 8), "query": query, "topic": topic})
        # Recent updates are chronological; other topic queries are relevance-ranked.
        if topic == "recent_updates":
            results.sort(key=lambda item: item["id"])
            results.sort(key=lambda item: datetime.fromisoformat(item["occurred_at"]), reverse=True)
        else:
            results.sort(key=lambda item: (-item["score"], item["id"]))
        return results[:limit]

    def snapshot(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "as_of": self.as_of.isoformat(),
            "record_versions": self.record_versions,
            "chunks": self.chunks,
        }

    @classmethod
    def restore(cls, snapshot: dict[str, Any]) -> MemoryIndex:
        index = cls(
            client_id=snapshot["client_id"], as_of=datetime.fromisoformat(snapshot["as_of"])
        )
        index.record_versions = snapshot["record_versions"]
        index.chunks = snapshot["chunks"]
        return index
