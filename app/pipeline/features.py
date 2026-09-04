"""Analytics adapters. Formulas remain owned by app.analytics.

The legacy adapter is transitional: it exposes existing analytics numerics as single Facts.
Member 4 supplies the Phase A provider for new Signal definitions and historical runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Protocol

from app.analytics.facts import AS_OF, fact_engine
from app.pipeline.schemas import Fact, FactBundle, SignalSet
from app.pipeline.sources import _has_fx_path
from app.pipeline.stages.clean import CleanedSources


@dataclass
class FeatureArtifacts:
    facts: dict[str, FactBundle]
    signals: dict[str, SignalSet]
    context_issues: list[str]


class AnalyticsProvider(Protocol):
    def __call__(self, sources: CleanedSources, run_id: str, /) -> FeatureArtifacts: ...


def legacy_analytics(sources: CleanedSources, run_id: str) -> FeatureArtifacts:
    """Adapt existing outputs without adding or changing any financial formulas."""
    if sources.as_of != AS_OF:
        raise ValueError("Historical analytics requires Member 4 Phase A provider")
    computed = {}
    context_issues = ["Phase A Signal definitions are not connected; legacy Facts only."]
    for client_id, client_tables in sources.clients.items():
        needs = client_tables["planned_cash_needs"].sort_values("due_from")
        holdings = client_tables["holdings"]
        current = holdings[holdings["snapshot_date"] == sources.as_of.isoformat()]
        if not needs.empty and not current.empty:
            source_currency = str(needs.iloc[0]["currency"])
            target_currency = str(current.iloc[0]["portfolio_ccy"])
            if source_currency != target_currency and any(
                not _has_fx_path(
                    sources.tables["market_context"], currency, sources.as_of.isoformat()
                )
                for currency in (source_currency, target_currency)
            ):
                computed[client_id] = []
                context_issues.append(
                    f"{client_id}: legacy Facts unavailable; required FX path is missing."
                )
                continue
        # The engine owns formulas; per-client invocation isolates unavailable source inputs.
        tables = {**sources.tables, "clients": client_tables["clients"]}
        client_facts, _ = fact_engine(tables, sources.as_of)
        computed.update(client_facts)
    bundles = {}
    for client_id, legacy_facts in computed.items():
        facts = []
        for legacy in legacy_facts:
            kind = legacy["id"].rsplit(":", 1)[-1]
            numbers = legacy["numbers"]
            for field, value in numbers.items():
                if isinstance(value, bool) or not isinstance(value, Real):
                    continue
                facts.append(
                    Fact(
                        id=f"{legacy['id']}:{field}",
                        client_id=client_id,
                        kind=f"{kind}.{field}",
                        value=float(value),
                        unit="percent"
                        if field.endswith("_pct")
                        else "days"
                        if field == "days"
                        else "number",
                        currency=numbers.get("currency") or numbers.get("portfolio_currency"),
                        formula_id=f"legacy.{kind}.{field}",
                        inputs=numbers,
                        evidence_ids=sorted(set(legacy["source_rows"] + legacy["event_ids"])),
                        as_of=sources.as_of,
                        confidence=1.0 if legacy["confidence"] == "high" else 0.5,
                    )
                )
        bundles[client_id] = FactBundle(
            client_id=client_id,
            as_of=sources.as_of,
            run_id=run_id,
            facts=sorted(facts, key=lambda item: item.id),
        )
    return FeatureArtifacts(
        facts=bundles,
        signals={
            client_id: SignalSet(client_id=client_id, as_of=sources.as_of, run_id=run_id)
            for client_id in bundles
        },
        context_issues=context_issues,
    )
