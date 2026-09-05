"""Member 2 outputs and provisional consumer contracts for the data team."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.pipeline.schemas import ContractModel, Evidence, Fact


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class Signal(ContractModel):
    id: str
    topic: str
    fact_ids: list[str] = Field(min_length=1)
    score: int = Field(ge=0, le=100)
    components: dict[str, int]
    uncertainty: str


class ChangeReport(ContractModel):
    previous_version: str | None = None
    changed_fact_ids: list[str] = Field(default_factory=list)
    changed_signal_ids: list[str] = Field(default_factory=list)


class CuratedClientBundle(ContractModel):
    """Provisional input: Member 3 publishes; Member 4 owns facts and scores."""

    schema_version: Literal[1] = 1
    client_id: str = Field(pattern=r"^CL-\d{4}$")
    as_of: date
    version: str
    facts: list[Fact] = Field(min_length=1)
    signals: list[Signal]
    evidence: dict[str, Evidence]
    quality_issues: list[str] = Field(default_factory=list)
    change_report: ChangeReport = Field(default_factory=ChangeReport)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        facts = {fact.id for fact in self.facts}
        if len(facts) != len(self.facts) or any(
            not fact_id.startswith(f"{self.client_id}:fact:") for fact_id in facts
        ):
            raise ValueError("Facts must be unique and belong to the requested client")
        if len({signal.id for signal in self.signals}) != len(self.signals):
            raise ValueError("Duplicate signal ID")
        if any(not set(signal.fact_ids) <= facts for signal in self.signals):
            raise ValueError("Signal references missing facts")
        if any(key != item.id for key, item in self.evidence.items()):
            raise ValueError("Evidence key does not match evidence ID")
        for fact in self.facts:
            if (
                not fact.source_rows
                or not set(fact.source_rows + fact.event_ids) <= self.evidence.keys()
            ):
                raise ValueError(f"Unresolved evidence for {fact.id}")
        return self

    def content_version(self) -> str:
        # The data team's version must cover facts, quality, signals and evidence.
        return fingerprint(self.model_dump(mode="json", exclude={"change_report"}))


class Claim(ContractModel):
    id: str
    text: str = Field(min_length=1, max_length=2000)
    citations: list[str] = Field(min_length=1)
    kind: Literal["fact", "memory", "suggestion", "uncertainty"]
    authorship: Literal["agent", "rm"] = "agent"


class Insight(ContractModel):
    signal_id: str
    score: int
    components: dict[str, int]
    facts: list[Claim]
    why_it_matters: Claim


class MeetingBrief(ContractModel):
    summary: list[Claim]
    opening: Claim
    talking_points: list[Claim]
    questions: list[Claim]
    uncertainty: list[Claim]


class MemorySection(ContractModel):
    claims: list[Claim] = Field(default_factory=list)
    evidence_gap: str | None = None


class ClientMemoryCard(ContractModel):
    who_they_are: MemorySection
    personality_and_style: MemorySection
    stated_needs_and_goals: MemorySection
    recent_updates: MemorySection
    open_promises: MemorySection
    advice_notes: MemorySection


class MeetingPack(ContractModel):
    client_id: str
    as_of: date
    input_versions: dict[str, str]
    insights: list[Insight] = Field(max_length=3)
    brief: MeetingBrief
    memory_card: ClientMemoryCard
    generation_mode: Literal["deterministic", "openai"] = "deterministic"

    @model_validator(mode="after")
    def unique_claims(self) -> Self:
        claims = self.claims()
        if len({c.id for c in claims}) != len(claims):
            raise ValueError("Meeting pack claim IDs must be unique")
        return self

    @property
    def version(self) -> str:
        return fingerprint(self.model_dump(mode="json"))

    def claims(self) -> list[Claim]:
        result = [
            self.brief.opening,
            *self.brief.summary,
            *self.brief.talking_points,
            *self.brief.questions,
            *self.brief.uncertainty,
        ]
        for insight in self.insights:
            result.extend([*insight.facts, insight.why_it_matters])
        for name in ClientMemoryCard.model_fields:
            result.extend(getattr(self.memory_card, name).claims)
        return result


class VerificationIssue(ContractModel):
    claim_id: str
    reason: str


class VerificationReport(ContractModel):
    pack_version: str
    passed: bool
    issues: list[VerificationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.passed == bool(self.issues):
            raise ValueError("Passing reports have no issues; failing reports require a reason")
        return self


class ReviewAction(ContractModel):
    client_id: str
    pack_version: str
    action: Literal["Approve", "Edit", "Reject", "Flag"]
    changes: dict[str, str] = Field(default_factory=dict)
    claim_id: str | None = None
    reason: str = ""

    @model_validator(mode="after")
    def fields_match_action(self) -> Self:
        if (self.action == "Edit") != bool(self.changes):
            raise ValueError("Only Edit accepts changes, and Edit requires changes")
        if any(not text.strip() or len(text) > 2000 for text in self.changes.values()):
            raise ValueError("Edited text must contain 1–2000 characters")
        if self.action == "Flag" and (not self.claim_id or not self.reason.strip()):
            raise ValueError("Flag requires a claim ID and reason")
        return self
