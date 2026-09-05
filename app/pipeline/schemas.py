"""Typed contracts shared by the pipeline, the API, and the review ledger.

The existing typed Fact contract is retained for agent inputs. Full artifact schemas
(CuratedClientBundle, FactBundle, SignalSet, EvidenceMap) remain a separate handoff.
"""

from __future__ import annotations

from datetime import datetime
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
