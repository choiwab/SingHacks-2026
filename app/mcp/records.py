"""Normalized communication records with explicit synthetic/live provenance."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from app.pipeline.schemas import ContractModel

Source = Literal["gmail", "outlook", "teams", "notes", "calendar"]
SOURCES: tuple[Source, ...] = ("gmail", "teams", "notes", "calendar")


class CommunicationRecord(ContractModel):
    id: str
    client_id: str
    source: Source
    version: str
    occurred_at: AwareDatetime
    retrieved_at: AwareDatetime
    scheduled_at: AwareDatetime | None = None
    participants: list[str] = Field(min_length=1)
    text: str = Field(min_length=1, max_length=20000)
    topics: list[str]
    provenance: Literal["synthetic_fixture", "dataset", "recorded_live"]
    availability: Literal["Cached", "Live"] = "Cached"
    based_on: list[str] = Field(default_factory=list)
    preference_key: str | None = None
    preference_value: str | None = None

    @model_validator(mode="after")
    def valid_provenance(self) -> Self:
        if not self.id.startswith(f"{self.source}:"):
            raise ValueError("Record ID must be namespaced by source")
        if self.provenance in {"synthetic_fixture", "dataset"} and self.availability == "Live":
            raise ValueError("Authored fixtures cannot claim a live retrieval")
        if bool(self.preference_key) != bool(self.preference_value):
            raise ValueError("Preference key and value must appear together")
        return self


class ConnectedContext(ContractModel):
    records: list[CommunicationRecord]
    sources: dict[str, Literal["Cached", "Live", "Not connected"]]
    retrieval_log: list[dict[str, str | list[str]]]

    @model_validator(mode="after")
    def availability_matches_records(self) -> Self:
        # Outlook is additive so existing offline fixtures retain their content hashes.
        if set(self.sources) not in (set(SOURCES), set(SOURCES) | {"outlook"}):
            raise ValueError("Every source must declare its availability")
        if any(r.source not in self.sources for r in self.records):
            raise ValueError("Record source must declare its availability")
        for source, status in self.sources.items():
            records = [r for r in self.records if r.source == source]
            if records and (
                status == "Not connected" or any(r.availability != status for r in records)
            ):
                raise ValueError("Source status contradicts record availability")
        return self
