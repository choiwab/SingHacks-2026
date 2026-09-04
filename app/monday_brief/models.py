"""Typed contract for a generated Monday Brief projection."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(ContractModel):
    id: str
    kind: str
    title: str
    source: str
    record: dict[str, Any]


class FactBase(ContractModel):
    id: str
    what: str
    source_rows: list[str]
    event_ids: list[str]
    confidence: Literal["high", "medium", "low"]


class ProfileNumbers(ContractModel):
    name: str
    currency: str
    language: str
    residence: str
    booking_centre: str
    risk_tolerance_score: int
    life_stage: str


class ProfileFact(FactBase):
    kind: Literal["profile"]
    numbers: ProfileNumbers


class ChangeNumbers(ContractModel):
    instrument: str
    delta: float
    currency: str


class ChangeFact(FactBase):
    kind: Literal["change"]
    numbers: ChangeNumbers


class MandateNumbers(ContractModel):
    asset_class: str
    actual_pct: float
    limit_pct: float
    boundary: Literal["minimum", "maximum"]
    gap_pct: float
    scope: str


class MandateFact(FactBase):
    kind: Literal["mandate_gap"]
    numbers: MandateNumbers


class DeadlineNumbers(ContractModel):
    days: int
    amount: float
    currency: str | None
    daily_liquid: float | None = None
    amount_in_portfolio_currency: float | None = None
    portfolio_currency: str | None = None
    coverage_pct: float | None = None
    description: str | None = None


class DeadlineFact(FactBase):
    kind: Literal["deadline"]
    numbers: DeadlineNumbers


class FacilityNumbers(ContractModel):
    ltv_pct: float
    trigger_pct: float
    gap_pct: float


class FacilityFact(FactBase):
    kind: Literal["facility"]
    numbers: FacilityNumbers


class ConcentrationNumbers(ContractModel):
    weight_pct: float
    value: float


class ConcentrationFact(FactBase):
    kind: Literal["concentration"]
    numbers: ConcentrationNumbers


Fact = Annotated[
    ProfileFact | ChangeFact | MandateFact | DeadlineFact | FacilityFact | ConcentrationFact,
    Field(discriminator="kind"),
]


class CitedText(ContractModel):
    text: str
    citations: list[str]


class Belief(CitedText):
    id: str
    note_id: str


class Gap(ContractModel):
    id: str
    belief: str
    data: str
    citations: list[str]


class WorkflowContext(ContractModel):
    system: str
    status: str
    citations: list[str]


class PreRead(ContractModel):
    client_id: str
    name: str
    language: str
    what_changed: list[CitedText]
    gap: Gap
    rules_money: list[CitedText]
    opening: CitedText
    uncertainty: CitedText
    beliefs: list[Belief]
    workflow: list[WorkflowContext]


class RankingComponents(ContractModel):
    gap: int
    deadline: int
    consequence: int


class Priority(ContractModel):
    client_id: str
    name: str
    score: int
    components: RankingComponents
    meeting: str | None
    meeting_source: str | None
    reason: str
    urgency: Literal["now", "soon", "watch"]
    citations: list[str]


class ScenarioBullet(CitedText):
    low_delta: float
    high_delta: float


class Scenario(ContractModel):
    name: str
    currency: str
    portfolio_value: float
    low_delta: float
    high_delta: float
    low_pct: float
    high_pct: float
    bullets: list[ScenarioBullet]
    citations: list[str]
    disclaimer: str


class ScenarioSet(ContractModel):
    reopens: Scenario
    escalates: Scenario


class MondayBriefProjection(ContractModel):
    schema_version: Literal[1] = 1
    as_of: date
    pipeline: list[str]
    ranking_formula: str
    ranking: list[Priority]
    facts: dict[str, list[Fact]]
    pre_reads: dict[str, PreRead]
    scenarios: dict[str, ScenarioSet]
    evidence: dict[str, Evidence]


class ReviewRequest(ContractModel):
    client_id: Annotated[str, Field(pattern=r"^CL-\d{4}$")]
    action: Literal["Approve", "Edit", "Reject"]
    text: Annotated[str, Field(max_length=1200)] = ""


class ReviewRecord(ReviewRequest):
    review_id: str
    rm: str
    timestamp: datetime


class ReviewResponse(ContractModel):
    review: ReviewRecord
