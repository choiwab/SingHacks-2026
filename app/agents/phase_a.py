"""Conservative conversation labels for the reviewed deterministic data contract."""

from app.agents.contracts import Signal
from app.pipeline.schemas import Fact
from app.pipeline.schemas import Signal as ArtifactSignal

LIMITATIONS = (
    "Reported marks may be stale. Income, fees and transaction cash flows are not reconciled "
    "to holdings, so mark changes are not total investment returns. Look-through uses "
    "non-additive product market values, not derivative notional. Currency exposure is "
    "assumed unhedged unless documented. Event associations are not proof of causation. "
    "Reference mappings and client intent require human Relationship Manager confirmation; "
    "these are discussion screens, not trade, suitability or tax advice."
)


def phase_a_signal(signal: ArtifactSignal) -> Signal:
    return Signal(
        id=signal.id,
        topic=signal.kind.replace("_", " ").replace(".", " "),
        fact_ids=signal.fact_ids,
        score=signal.priority_score,
        components=signal.score_components,
        uncertainty=LIMITATIONS,
        kind=signal.kind,
        severity=signal.severity,
        evidence_ids=signal.evidence_ids,
        metadata=signal.threshold if isinstance(signal.threshold, dict) else {},
    )


def phase_a_fact_description(fact: Fact) -> str:
    label = fact.kind.replace(".", " / ").replace("_", " ")
    qualifiers = [
        str(fact.inputs[key])
        for key in (
            "asset_class",
            "portfolio_id",
            "instrument_id",
            "issuer",
            "facility_id",
            "channel",
        )
        if fact.inputs.get(key)
    ]
    context = f" ({'; '.join(qualifiers)})" if qualifiers else ""
    unit = {"percent": "%", "percentage_points": "percentage points", "ratio": "times"}.get(
        fact.unit, fact.currency or fact.unit
    )
    return f"{label}{context}: {fact.value:g} {unit}."
