"""Public application projection built from persisted, run-scoped records."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, JsonValue

from app.pipeline.schemas import (
    ChangeReport,
    ContractModel,
    DataQualityFinding,
    Evidence,
    Fact,
    ReviewRecord,
)


class DataTab(ContractModel):
    allocation: list[Fact] = Field(default_factory=list)
    snapshot_changes: list[Fact] = Field(default_factory=list)
    mandate: list[Fact] = Field(default_factory=list)
    liquidity: list[Fact] = Field(default_factory=list)
    cash_need: list[Fact] = Field(default_factory=list)
    collateral: list[Fact] = Field(default_factory=list)


class ClientHeader(ContractModel):
    """Qualitative profile fields; financial numbers are presented as Facts."""

    client_id: str
    client_name: str
    rm_id: str
    rm_name: str
    rm_desk: str
    base_currency: str
    risk_profile: str
    life_stage: str
    reporting_language: str
    booking_centre: str


class ClientView(ContractModel):
    header: ClientHeader
    insights: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=3)
    meeting_brief: dict[str, JsonValue] | None = None
    brief_version: int | None = None
    memory_card: dict[str, JsonValue] | None = None
    data_tab: DataTab
    memory_tab: list[dict[str, JsonValue]] = Field(default_factory=list)
    change_report: ChangeReport
    quality_findings: list[DataQualityFinding] = Field(default_factory=list)
    brief_status: Literal["Ready", "Needs review", "Not prepared"]
    verification: dict[str, JsonValue] = Field(default_factory=dict)
    context_issues: list[str] = Field(default_factory=list)


class DemoViewModel(ContractModel):
    as_of: date
    run_id: str
    refreshed_at: datetime
    data_health: Literal["Current", "Stale", "Updating", "Needs confirmation"]
    clients: dict[str, ClientView]
    calendar: list[dict[str, JsonValue]] = Field(default_factory=list)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    reviews: list[ReviewRecord] = Field(default_factory=list)
