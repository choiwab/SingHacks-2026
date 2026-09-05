"""Deterministic provider and Evidence boundary for the reviewed Phase A formulas."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from app.pipeline.evidence import evidence_id, slug
from app.pipeline.schemas import Fact, FactBundle, Signal, SignalSet
from app.pipeline.stages.clean import CleanedSources

REFERENCE_MAP_PATH = Path(__file__).resolve().parents[2] / "notebooks" / "reference_maps.json"
FORMULA_VERSION = "phase-a-rm-review-v1"
PRIORITY_BY_SEVERITY = {"low": 20.0, "medium": 50.0, "high": 80.0, "critical": 100.0}


def _native(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_native(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if value is pd.NA or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class PhaseAContext:
    """Shared source-only calculations and typed artifact emission for one Pipeline Run."""

    def __init__(self, sources: CleanedSources, run_id: str):
        self.sources = sources
        self.tables = sources.tables
        self.run_id = run_id
        self.asof = sources.as_of
        self.as_of = sources.as_of
        self.clients = sources.tables["clients"]
        self.portfolios = sources.tables["portfolios"]
        self.instruments = sources.tables["instruments"]
        self.mandates = sources.tables["mandates"]
        cutoff = self.asof.isoformat()
        self.holdings = (
            sources.tables["holdings"]
            .loc[sources.tables["holdings"]["snapshot_date"].le(cutoff)]
            .copy()
        )
        snapshots = sorted(self.holdings["snapshot_date"].unique())
        self.snapshot = str(snapshots[-1]) if snapshots else cutoff
        self.baseline = str(snapshots[0]) if snapshots else cutoff
        self.latest = self.holdings.loc[self.holdings["snapshot_date"].eq(self.snapshot)].copy()
        self.notes = {
            note["note_id"]: dict(note)
            for note in sources.notes
            if str(note["note_date"]) <= cutoff
        }
        self.client_names = self.clients.set_index("client_id")["client_name"].to_dict()
        self.base_ccy = self.clients.set_index("client_id")["base_currency"].to_dict()
        self.context_issues = [
            "Phase A analytical mappings and policies require responsible human RM approval "
            "before client use. Income and fees are not reconciled to positions."
        ]
        if self.snapshot != cutoff:
            self.context_issues.append(
                f"Latest holdings/FX observation is {self.snapshot}, before As-of Date {cutoff}."
            )
        mapping = json.loads(REFERENCE_MAP_PATH.read_text())
        self.reference_effective_date = date.fromisoformat(mapping["effective_as_of"])
        self.reference_maps = mapping if mapping["effective_as_of"] <= cutoff else {}
        if not self.reference_maps:
            self.context_issues.append(
                "Reviewed reference map is not effective at this As-of Date; "
                "mapped claims withheld."
            )
        self.facts: dict[str, list[Fact]] = {client: [] for client in self.client_names}
        self.signals: dict[str, list[Signal]] = {client: [] for client in self.client_names}
        self.performance = pd.DataFrame(index=list(self.client_names))
        self.income_summary = pd.DataFrame(index=list(self.client_names))
        self.same_store_base_values = pd.DataFrame(index=list(self.client_names))
        self.liquidity = pd.DataFrame(index=list(self.client_names))
        self._identifiers: set[str] = set()
        self.source_evidence_ids = {
            evidence_id(table, row)
            for table, frame in sources.tables.items()
            if table not in {"fx_rates", "holdings_reconciliation", "issuer_map", "lookthrough_map"}
            for _, row in frame.iterrows()
        } | {f"rm_notes:{note_id}" for note_id in self.notes}

    def evidence(self, table: str, frame: pd.DataFrame) -> list[str]:
        return sorted({evidence_id(table, row) for _, row in frame.iterrows()})

    def holding_evidence(self, frame: pd.DataFrame) -> list[str]:
        return self.evidence("holdings", frame)

    def _fx_row(self, currency: str, snapshot: str | None = None) -> pd.Series:
        snapshot = snapshot or self.snapshot
        if snapshot > self.asof.isoformat():
            raise ValueError("Future FX observations cannot support a Phase A Fact")
        market = self.tables["market_context"]
        rows = market.loc[
            market["snapshot_date"].eq(snapshot)
            & market["category"].eq("FX")
            & market["series_id"].isin([f"{currency}USD", f"USD{currency}"])
        ]
        if rows.empty:
            raise ValueError(f"Missing FX path for {currency} at {snapshot}")
        row = rows.sort_values("series_id").iloc[0]
        if not math.isfinite(float(row["value"])) or float(row["value"]) <= 0:
            raise ValueError(f"Invalid FX quote for {currency} at {snapshot}")
        return row

    def to_usd(self, amount: float, currency: str, snapshot: str | None = None) -> float:
        if currency == "USD":
            return float(amount)
        row = self._fx_row(currency, snapshot)
        factor = float(row["value"])
        return float(amount) * factor if row["series_id"] == f"{currency}USD" else amount / factor

    def fx_evidence(self, currency: str, snapshot: str | None = None) -> list[str]:
        return (
            []
            if currency == "USD"
            else [evidence_id("market_context", self._fx_row(currency, snapshot))]
        )

    def _evidence(self, identifiers: Iterable[str]) -> list[str]:
        result = sorted(set(identifiers))
        missing = set(result) - self.source_evidence_ids
        if missing:
            raise ValueError(f"Phase A references unknown source Evidence: {sorted(missing)}")
        if not result:
            raise ValueError("Every Phase A Fact or Signal needs original source Evidence")
        return result

    def emit_fact(
        self,
        client_id: str,
        kind: str,
        value: float,
        *,
        scope: str = "",
        unit: str = "number",
        currency: str | None = None,
        inputs: dict | None = None,
        evidence_ids: Iterable[str] = (),
        confidence: float = 1.0,
    ) -> Fact:
        if not math.isfinite(float(value)):
            raise ValueError("Every Phase A Fact value must be finite")
        identifier = f"{client_id}:fact:{kind}" + (f":{slug(scope)}" if scope else "")
        if identifier in self._identifiers:
            raise ValueError(f"Duplicate Phase A Fact identifier {identifier}")
        fact = Fact(
            id=identifier,
            client_id=client_id,
            kind=kind,
            value=float(value),
            unit=unit,
            currency=currency,
            formula_id=f"{FORMULA_VERSION}.{kind}",
            inputs=_native(inputs or {}),
            evidence_ids=self._evidence(evidence_ids),
            as_of=self.asof,
            confidence=confidence,
        )
        self.facts[client_id].append(fact)
        self._identifiers.add(identifier)
        return fact

    def emit_signal(
        self,
        client_id: str,
        kind: str,
        severity: str,
        *,
        scope: str = "",
        fact_ids: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
        threshold: Any = None,
    ) -> Signal:
        identifier = f"{client_id}:signal:{kind}" + (f":{slug(scope)}" if scope else "")
        if identifier in self._identifiers:
            raise ValueError(f"Duplicate Phase A Signal identifier {identifier}")
        requested_facts = sorted(set(fact_ids))
        available = {fact.id: fact for fact in self.facts[client_id]}
        if set(requested_facts) - available.keys():
            raise ValueError("Signal references unavailable or another Client's Facts")
        resolved = set(evidence_ids)
        for fact_id in requested_facts:
            resolved.update(available[fact_id].evidence_ids)
        priority = PRIORITY_BY_SEVERITY[severity]
        signal = Signal(
            id=identifier,
            client_id=client_id,
            kind=kind,
            severity=severity,
            priority_score=priority,
            score_components={"severity_policy": priority},
            threshold=_native(threshold),
            fact_ids=requested_facts,
            evidence_ids=self._evidence(resolved),
            as_of=self.asof,
        )
        self.signals[client_id].append(signal)
        self._identifiers.add(identifier)
        return signal


def phase_a_analytics(sources: CleanedSources, run_id: str):
    """Compute the reviewed specification without executing or importing notebook code."""
    from app.analytics.phase_a_funding import compute_funding
    from app.analytics.phase_a_mandates import compute_mandates
    from app.analytics.phase_a_performance import compute_performance
    from app.analytics.phase_a_risk import compute_risk
    from app.pipeline.features import FeatureArtifacts

    context = PhaseAContext(sources, run_id)
    compute_performance(context)
    compute_mandates(context)
    compute_funding(context)
    compute_risk(context)
    return FeatureArtifacts(
        facts={
            client_id: FactBundle(
                client_id=client_id,
                as_of=context.asof,
                run_id=run_id,
                facts=sorted(facts, key=lambda fact: fact.id),
            )
            for client_id, facts in context.facts.items()
        },
        signals={
            client_id: SignalSet(
                client_id=client_id,
                as_of=context.asof,
                run_id=run_id,
                signals=sorted(signals, key=lambda signal: (-signal.priority_score, signal.id)),
            )
            for client_id, signals in context.signals.items()
        },
        context_issues=sorted(set(context.context_issues)),
    )
