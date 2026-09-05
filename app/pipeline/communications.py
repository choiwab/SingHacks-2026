"""Pinned communication snapshots with content identities independent of polling."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from typing import Self

from pydantic import Field, model_validator

from app.mcp.records import ConnectedContext
from app.pipeline.schemas import ContractModel


class CommunicationSnapshot(ContractModel):
    client_id: str = Field(pattern=r"^CL-\d{4}$")
    as_of: date
    context: ConnectedContext

    @model_validator(mode="after")
    def scoped_records(self) -> Self:
        cutoff = datetime.combine(self.as_of, time.max, UTC)
        records = self.context.records
        if any(record.client_id != self.client_id for record in records):
            raise ValueError("Communication snapshot contains another client's record")
        if any(record.occurred_at > cutoff for record in records):
            raise ValueError("Communication snapshot contains a future record")
        if len({record.id for record in records}) != len(records):
            raise ValueError("Communication snapshot contains duplicate record IDs")
        return self

    @property
    def revision(self) -> str:
        """Hash substantive inputs without changing the original persisted snapshot."""
        content = self.model_dump(mode="json")
        context = content["context"]
        context.pop("retrieval_log")
        context["records"] = sorted(context["records"], key=lambda record: record["id"])
        for record in context["records"]:
            record.pop("retrieved_at")
        encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode()).hexdigest()
