"""Typed contracts shared by the pipeline, the API, and the review ledger.

Full artifact schemas (CuratedClientBundle, FactBundle, SignalSet, EvidenceMap) are a
separate issue and do not live here yet.
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
