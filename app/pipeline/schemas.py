"""Typed source, artifact, API, and review-ledger contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(ContractModel):
    id: str
    kind: str
    title: str
    source: str
    record: dict[str, Any]
    source_file: str = ""
    row_index: int | None = None
    fields: dict[str, JsonValue] = Field(default_factory=dict)


class ReviewRequest(ContractModel):
    client_id: Annotated[str, Field(pattern=r"^CL-\d{4}$")]
    action: Literal["Approve", "Edit", "Reject"]
    run_id: str | None = None
    brief_version: Annotated[int | None, Field(ge=1)] = None
    section: str | None = None
    reason: str | None = None
    text: Annotated[str, Field(max_length=1200)] = ""


class ReviewRecord(ReviewRequest):
    verification_report_id: str | None = None
    review_id: str
    rm: str
    timestamp: datetime


class ReviewResponse(ContractModel):
    review: ReviewRecord


class Artifact(ContractModel):
    """Deterministic artifact envelope. Empty run_id is allowed before publication."""

    as_of: date
    run_id: str = ""


class Fact(ContractModel):
    id: str
    client_id: str
    kind: str
    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: str
    currency: str | None = None
    formula_id: str
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    as_of: date
    confidence: Annotated[float, Field(ge=0, le=1)]


class FactBundle(Artifact):
    client_id: str
    facts: list[Fact] = Field(default_factory=list)
    # The engine's own sentence for each measurement, keyed by the leading Fact of the group
    # it was split into. Agents read this instead of re-deriving prose from the numbers.
    descriptions: dict[str, str] = Field(default_factory=dict)


class Signal(ContractModel):
    id: str
    client_id: str
    kind: str
    severity: Literal["low", "medium", "high", "critical"]
    priority_score: float
    score_components: dict[str, float] = Field(default_factory=dict)
    threshold: JsonValue = None
    fact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    as_of: date


class SignalSet(Artifact):
    client_id: str
    signals: list[Signal] = Field(default_factory=list)


class EvidenceMap(Artifact):
    entries: dict[str, Evidence] = Field(default_factory=dict)


class DataQualityFinding(ContractModel):
    code: str
    severity: Literal["error", "warning"]
    client_id: str | None = None
    portfolio_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    message: str


class DataQualityReport(Artifact):
    findings: list[DataQualityFinding] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(finding.severity == "error" for finding in self.findings)

    @property
    def error_count(self) -> int:
        return sum(finding.severity == "error" for finding in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(finding.severity == "warning" for finding in self.findings)


class FactChange(ContractModel):
    fact_id: str
    change: Literal["added", "removed", "changed"]
    before: float | None = None
    after: float | None = None


class SignalChange(ContractModel):
    signal_id: str
    change: Literal["added", "removed", "changed"]
    before: str | None = None
    after: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    before_priority_score: float | None = None
    after_priority_score: float | None = None
    before_threshold: JsonValue = None
    after_threshold: JsonValue = None


class ChangeReport(Artifact):
    client_id: str
    prior_run_id: str | None = None
    processing_mode: Literal["first_seen", "incremental_update", "no_material_change"]
    fact_changes: list[FactChange] = Field(default_factory=list)
    signal_changes: list[SignalChange] = Field(default_factory=list)
    changed_fact_ids: list[str] = Field(default_factory=list)
    affected_signal_ids: list[str] = Field(default_factory=list)
    changed_source_files: list[str] = Field(default_factory=list)
    changed_context_sections: list[str] = Field(default_factory=list)


class RunManifest(Artifact):
    pipeline_version: str
    git_sha: str
    source_hashes: dict[str, str]
    overlay_hashes: dict[str, str] = Field(default_factory=dict)
    overridden_keys: dict[str, list[str]] = Field(default_factory=dict)
    client_ids: list[str]
    finding_counts: dict[str, int] = Field(default_factory=dict)
    context_issues: list[str] = Field(default_factory=list)
    created_at: datetime


class ClientProfile(ContractModel):
    client_id: str
    client_name: str
    age: int | None
    gender: str
    nationality: str
    country_of_residence: str
    tax_domicile: str
    booking_centre: str
    rm_id: str
    rm_name: str
    rm_desk: str
    base_currency: str
    wealth_band: str
    total_aum_usd: float | None = None
    life_stage: str
    source_of_wealth: str
    risk_profile: str
    risk_tolerance_score: int
    investment_horizon_years: float
    liquidity_needs: str
    objectives: str
    client_since: date
    kyc_review_due: date
    pep_status: str
    reporting_language: str


class Portfolio(ContractModel):
    portfolio_id: str
    client_id: str
    portfolio_name: str
    mandate_code: str
    mandate_name: str
    service_model: str
    base_currency: str
    inception_date: date
    benchmark: str
    aum_by_date: dict[date, float] = Field(default_factory=dict)
    aum_usd_current: float | None = None


class Holding(ContractModel):
    snapshot_date: date
    portfolio_id: str
    client_id: str
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str
    region: str
    instrument_ccy: str
    quantity: float
    price_local: float
    market_value_local: float
    portfolio_ccy: str
    market_value_base: float
    market_value_usd: float
    weight_pct: float
    avg_cost_local: float | None
    cost_basis_base: float | None
    unrealised_pnl_base: float | None
    unrealised_pnl_pct: float | None
    lending_value_base: float
    advance_rate_pct: float
    liquidity_tier: str
    valuation_date: date
    acquired_date: date


class MandateRule(ContractModel):
    mandate_code: str
    mandate_name: str
    asset_class: str
    min_pct: float
    target_pct: float
    max_pct: float
    max_single_position_pct: float
    mandate_notes: str


class CashNeed(ContractModel):
    need_id: str
    client_id: str
    description: str
    currency: str
    amount: float
    due_from: date
    due_to: date
    recurrence: str
    certainty: str


class CreditSnapshot(ContractModel):
    snapshot_date: date
    drawn: float
    collateral_market_value: float
    lending_value: float
    ltv_pct: float
    headroom: float


class CreditFacility(ContractModel):
    facility_id: str
    client_id: str
    collateral_portfolio_id: str
    facility_type: str
    facility_ccy: str
    credit_limit: float
    interest_rate_pct: float
    margin_call_ltv_pct: float
    snapshots: list[CreditSnapshot] = Field(default_factory=list)
    utilisation_pct_current: float | None = None


class Commitment(ContractModel):
    commitment_id: str
    client_id: str
    portfolio_id: str
    fund_name: str
    currency: str
    committed: float
    called_to_date: float
    uncalled: float
    expected_call_window: str


class RMNote(ContractModel):
    note_id: str
    client_id: str
    note_date: date
    rm_id: str
    rm_name: str
    channel: str
    note: str
    evidence_id: str


class LiquidityPosition(ContractModel):
    snapshot_date: date
    portfolio_id: str
    instrument_id: str
    liquidity_tier: str
    market_value_base: float
    currency: str
    evidence_ids: list[str] = Field(default_factory=list)


class CuratedClientBundle(Artifact):
    client_id: str
    profile: ClientProfile
    portfolios: list[Portfolio] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    mandate_rules: list[MandateRule] = Field(default_factory=list)
    liquidity: list[LiquidityPosition] = Field(default_factory=list)
    credit: list[CreditFacility] = Field(default_factory=list)
    cash_needs: list[CashNeed] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    rm_notes: list[RMNote] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    signal_ids: list[str] = Field(default_factory=list)
