"""Per-managed-Portfolio allocation, position and binding-exclusion rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.analytics.phase_a import PhaseAContext

ASSET_CLASSES = {
    "Cash and Equivalents",
    "Fixed Income",
    "Equity",
    "Alternatives",
    "Commodities",
    "Structured Products",
}


def band_gap(actual: float, minimum: float, maximum: float) -> float:
    return max(actual - maximum, 0.0) + min(actual - minimum, 0.0)


def breach_classification(
    context: PhaseAContext,
    client_id: str,
    kind: str,
    asset_class: str,
    instrument_id: str | None = None,
) -> dict:
    result = {
        "classification": "drift",
        "note_id": None,
        "classification_status": "provisional routing; cause unestablished",
        "action": "RM investigates cause and documents remediation advice",
        "classification_basis": "No supporting instruction or waiver located; not proven drift",
    }
    candidates = []
    if client_id == "CL-0003":
        candidates = [("N-005", "not make any changes", "client-directed")]
    elif client_id == "CL-0007" and asset_class == "Commodities":
        candidates = [("N-010", "waiver on file", "waiver-on-file")]
    elif client_id == "CL-0009":
        if kind == "mandate_band_breach" and asset_class == "Cash and Equivalents":
            candidates = [("N-013", "waiting for a better entry point", "client-directed")]
        elif instrument_id == "SYN-ST-0107":
            candidates = [("N-013", "unwilling to sell", "client-directed")]
    for note_id, required_text, classification in candidates:
        note = context.notes.get(note_id)
        if note and note["client_id"] == client_id and required_text in note["note"].lower():
            result.update(
                {
                    "classification": classification,
                    "note_id": note_id,
                    "classification_status": "documented context; confirm scope and currency",
                    "classification_basis": f"RM note {note_id} of {note['note_date']}",
                    "action": "Monitor and confirm waiver current"
                    if classification == "waiver-on-file"
                    else "Alert stands; document advice and re-solicit the client instruction",
                }
            )
    if kind == "mandate_exclusion_breach":
        result.update(
            {
                "documentation_failure": True,
                "classification_status": (
                    "provisional routing; documentation failure, not market drift"
                ),
                "action": "Escalate binding exclusion; reconcile policy and document remediation",
            }
        )
        note = context.notes.get("N-008")
        if note and note["client_id"] == client_id:
            result["note_id"] = "N-008"
            result["classification_basis"] = "RM note N-008; not an exclusion override instruction"
    return result


def compute_mandates(context: PhaseAContext) -> None:
    managed = context.portfolios.loc[context.portfolios["service_model"].ne("Custody")]
    instrument_lookup = context.instruments.set_index("instrument_id")
    for portfolio in managed.itertuples():
        client_id = portfolio.client_id
        if client_id not in context.facts:
            continue
        holdings = context.latest.loc[context.latest["portfolio_id"].eq(portfolio.portfolio_id)]
        rules = context.mandates.loc[context.mandates["mandate_code"].eq(portfolio.mandate_code)]
        if set(rules["asset_class"]) != ASSET_CLASSES or rules["asset_class"].duplicated().any():
            raise ValueError(f"Incomplete or duplicated six-class Mandate {portfolio.mandate_code}")
        total = float(holdings["market_value_base"].sum())
        if holdings.empty or total <= 0:
            context.context_issues.append(
                f"{portfolio.portfolio_id}: no positive snapshot value for Mandate tests."
            )
            continue
        denominator_evidence = context.holding_evidence(holdings) + [
            f"portfolios:{portfolio.portfolio_id}"
        ]
        rule_lookup = rules.set_index("asset_class")
        for rule in rules.itertuples():
            value = float(
                holdings.loc[
                    holdings["asset_class"].eq(rule.asset_class), "market_value_base"
                ].sum()
            )
            actual = value / total * 100
            gap = band_gap(actual, rule.min_pct, rule.max_pct)
            metadata = {
                "portfolio_id": portfolio.portfolio_id,
                "mandate_code": portfolio.mandate_code,
                "asset_class": rule.asset_class,
                "min_pct": rule.min_pct,
                "max_pct": rule.max_pct,
                "portfolio_total_base": total,
                "asset_class_value_base": value,
                "snapshot": context.snapshot,
                "basis": "per managed Portfolio market_value_base",
                **breach_classification(
                    context, client_id, "mandate_band_breach", rule.asset_class
                ),
            }
            evidence = denominator_evidence + context.evidence(
                "mandates", rules.loc[rules["asset_class"].eq(rule.asset_class)]
            )
            if metadata["note_id"]:
                evidence.append(f"rm_notes:{metadata['note_id']}")
            scope = f"{portfolio.portfolio_id}:{rule.asset_class}"
            fact = context.emit_fact(
                client_id,
                "mandate.allocation_pct",
                actual,
                scope=scope,
                unit="percent",
                evidence_ids=evidence,
                inputs=metadata,
            )
            minimum_fact = context.emit_fact(
                client_id,
                "mandate.minimum_pct",
                rule.min_pct,
                scope=scope,
                unit="percent",
                evidence_ids=evidence,
                inputs=metadata,
            )
            maximum_fact = context.emit_fact(
                client_id,
                "mandate.maximum_pct",
                rule.max_pct,
                scope=scope,
                unit="percent",
                evidence_ids=evidence,
                inputs=metadata,
            )
            if gap:
                gap_fact = context.emit_fact(
                    client_id,
                    "mandate.band_gap_pp",
                    gap,
                    scope=scope,
                    unit="percentage_points",
                    evidence_ids=evidence,
                    inputs=metadata,
                )
                context.emit_signal(
                    client_id,
                    "mandate_band_breach",
                    "high" if abs(gap) > 10 else "medium",
                    scope=scope,
                    fact_ids=[
                        fact.id,
                        gap_fact.id,
                        maximum_fact.id if gap > 0 else minimum_fact.id,
                    ],
                    threshold={**metadata, "high_above_gap_pp": 10},
                )
        for position in holdings.itertuples():
            instrument = instrument_lookup.loc[position.instrument_id]
            rule = rule_lookup.loc[position.asset_class]
            evidence = denominator_evidence + [f"instruments:{position.instrument_id}"]
            evidence += context.evidence(
                "mandates", rules.loc[rules["asset_class"].eq(position.asset_class)]
            )
            actual = float(position.market_value_base) / total * 100
            scope = f"{portfolio.portfolio_id}:{position.instrument_id}"
            metadata = {
                "portfolio_id": portfolio.portfolio_id,
                "mandate_code": portfolio.mandate_code,
                "instrument_id": position.instrument_id,
                "snapshot": context.snapshot,
                "portfolio_total_base": total,
                "basis": "per managed Portfolio market_value_base",
            }
            if instrument["concentration_limit_applies"] == "Y":
                limit = float(rule["max_single_position_pct"])
                classification = breach_classification(
                    context,
                    client_id,
                    "mandate_single_position_breach",
                    position.asset_class,
                    position.instrument_id,
                )
                position_evidence = evidence.copy()
                if classification["note_id"]:
                    position_evidence.append(f"rm_notes:{classification['note_id']}")
                position_inputs = {**metadata, **classification, "max_single_position_pct": limit}
                fact = context.emit_fact(
                    client_id,
                    "mandate.single_position_pct",
                    actual,
                    scope=scope,
                    unit="percent",
                    evidence_ids=position_evidence,
                    inputs=position_inputs,
                )
                limit_fact = context.emit_fact(
                    client_id,
                    "mandate.single_position_limit_pct",
                    limit,
                    scope=scope,
                    unit="percent",
                    evidence_ids=position_evidence,
                    inputs=position_inputs,
                )
                if actual > limit:
                    gap_fact = context.emit_fact(
                        client_id,
                        "mandate.single_position_gap_pp",
                        actual - limit,
                        scope=scope,
                        unit="percentage_points",
                        evidence_ids=position_evidence,
                        inputs=position_inputs,
                    )
                    context.emit_signal(
                        client_id,
                        "mandate_single_position_breach",
                        "high" if actual - limit > 2 else "medium",
                        scope=scope,
                        fact_ids=[fact.id, gap_fact.id, limit_fact.id],
                        threshold={**position_inputs, "high_above_gap_pp": 2},
                    )
            binding_exclusions = "binding exclusions" in str(rule["mandate_notes"]).lower()
            if (
                binding_exclusions
                and instrument["sustainability_excluded"] == "Y"
                and position.quantity > 0
            ):
                classification = breach_classification(
                    context,
                    client_id,
                    "mandate_exclusion_breach",
                    position.asset_class,
                    position.instrument_id,
                )
                if classification["note_id"]:
                    evidence.append(f"rm_notes:{classification['note_id']}")
                inputs = {**metadata, **classification, "binding_exclusion": True}
                fact = context.emit_fact(
                    client_id,
                    "mandate.excluded_position_pct",
                    actual,
                    scope=scope,
                    unit="percent",
                    evidence_ids=evidence,
                    inputs=inputs,
                )
                context.emit_signal(
                    client_id,
                    "mandate_exclusion_breach",
                    "high",
                    scope=scope,
                    fact_ids=[fact.id],
                    threshold={**inputs, "holding_quantity_above": 0},
                )
