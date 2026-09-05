"""Source-evidenced Phase A concentration, credit, event and suitability screens."""

from __future__ import annotations

import re
from itertools import pairwise
from typing import TYPE_CHECKING

import pandas as pd

from app.pipeline.evidence import evidence_id

if TYPE_CHECKING:
    from app.analytics.phase_a import PhaseAContext


def compute_risk(context: PhaseAContext) -> None:
    """Append deterministic Facts and Signals using only eligible source observations."""
    engine = _RiskEngine(context)
    engine.concentration()
    engine.collateral()
    engine.currency()
    engine.events()
    engine.suitability()


class _RiskEngine:
    def __init__(self, context: PhaseAContext) -> None:
        self.context = context
        self.maps = context.reference_maps
        self.lookthrough = self.maps.get("lookthrough", {})
        self.instruments = context.instruments.set_index("instrument_id", drop=False)
        self.households = {
            client_id: frame for client_id, frame in context.latest.groupby("client_id")
        }
        self.totals = context.latest.groupby("client_id")["market_value_usd"].sum()
        self.available = {
            identifier
            for table, frame in context.tables.items()
            if table
            in {
                "clients",
                "portfolios",
                "holdings",
                "instruments",
                "mandates",
                "transactions",
                "credit_facilities",
                "commitments",
                "planned_cash_needs",
                "market_context",
                "event_log",
            }
            for identifier in context.evidence(table, frame)
        } | {f"rm_notes:{identifier}" for identifier in context.notes}
        self.missing_baskets: dict[str, list[dict]] = {}

    def map_inputs(self) -> dict:
        return {
            "mapping_version": self.maps.get("mapping_version"),
            "mapping_review_status": self.maps.get(
                "review_status", "Reference map unavailable at this as-of date"
            ),
            "snapshot_date": self.context.snapshot,
        }

    def household_evidence(self, client_id: str) -> list[str]:
        return self.context.holding_evidence(self.households[client_id])

    def qualified_override(self, section: str, client_id: str) -> dict:
        candidate = self.maps.get(section, {}).get(client_id, {})
        references = set(candidate.get("evidence_ids", []))
        return candidate if references and references <= self.available else {}

    def channel_instruments(self, channel: str) -> set[str]:
        definition = self.maps["channels"][channel]
        members = set(definition["instrument_ids"])
        if "instrument_currency" in definition:
            members.update(
                self.instruments.loc[
                    self.instruments["currency"].eq(definition["instrument_currency"]),
                    "instrument_id",
                ]
            )
        return members | {
            note_id
            for note_id, mapping in self.lookthrough.items()
            if members.intersection(mapping["underlying_ids"])
        }

    def instrument_evidence(self, members: set[str]) -> list[str]:
        references = members | {
            underlying
            for note_id in members
            for underlying in self.lookthrough.get(note_id, {}).get("underlying_ids", [])
        }
        return sorted(
            f"instruments:{identifier}"
            for identifier in references
            if f"instruments:{identifier}" in self.available
        )

    def concentration(self) -> None:
        context = self.context
        issuers = {
            row.instrument_id: row.instrument_id
            for row in context.instruments.itertuples()
            if row.concentration_limit_applies == "Y"
        }
        issuers.update(self.maps.get("issuer_overrides", {}))
        managed = context.portfolios.loc[context.portfolios["service_model"].ne("Custody")]
        limit_rows = managed.merge(
            context.mandates[["mandate_code", "max_single_position_pct"]].drop_duplicates(),
            on="mandate_code",
        )
        limits = limit_rows.groupby("client_id")["max_single_position_pct"].min()
        for client_id, household in self.households.items():
            total = float(self.totals[client_id])
            if total <= 0:
                continue
            self._unknown_baskets(client_id, household, total)
            codes = set(limit_rows.loc[limit_rows["client_id"].eq(client_id), "mandate_code"])
            mandate_evidence = context.evidence(
                "mandates", context.mandates.loc[context.mandates["mandate_code"].isin(codes)]
            )
            portfolio_evidence = context.evidence(
                "portfolios", managed.loc[managed["client_id"].eq(client_id)]
            )
            for issuer in sorted(set(issuers.values())):
                members = {identifier for identifier, name in issuers.items() if name == issuer}
                direct_members = members - self.lookthrough.keys()
                note_members = (members & self.lookthrough.keys()) | {
                    note_id
                    for note_id, mapping in self.lookthrough.items()
                    if any(
                        issuers.get(underlying) == issuer
                        for underlying in mapping["underlying_ids"]
                    )
                }
                direct = float(
                    household.loc[
                        household["instrument_id"].isin(direct_members), "market_value_usd"
                    ].sum()
                )
                indirect = float(
                    household.loc[
                        household["instrument_id"].isin(note_members), "market_value_usd"
                    ].sum()
                )
                if direct + indirect <= 0:
                    continue
                held_members = set(
                    household.loc[
                        household["instrument_id"].isin(direct_members | note_members),
                        "instrument_id",
                    ]
                )
                citations = self.household_evidence(client_id)
                citations += self.instrument_evidence(held_members)
                citations += mandate_evidence + portfolio_evidence
                disclosures = [
                    self.lookthrough[note_id]["disclosure"]
                    for note_id in sorted(held_members & self.lookthrough.keys())
                ]
                inputs = {
                    **self.map_inputs(),
                    "issuer": issuer,
                    "household_usd": total,
                    "direct_market_value_usd": direct,
                    "indirect_market_value_usd": indirect,
                    "attribution_basis": "per_name_full_current_market_value_non_additive",
                    "disclosure": "Do not sum across issuers; not delta, notional or maximum loss",
                    "product_disclosures": disclosures,
                    "incomplete_lookthrough": self.missing_baskets.get(client_id, []),
                    "compliance_finding": False,
                }
                facts = [
                    context.emit_fact(
                        client_id,
                        f"concentration.{field}",
                        value / total * 100,
                        scope=issuer,
                        unit="percent",
                        inputs=inputs,
                        evidence_ids=citations,
                    )
                    for field, value in [
                        ("direct_pct", direct),
                        ("indirect_pct", indirect),
                        ("lookthrough_pct", direct + indirect),
                    ]
                ]
                limit = float(limits[client_id]) if client_id in limits.index else None
                if limit is not None:
                    facts.append(
                        context.emit_fact(
                            client_id,
                            "concentration.household_reference_limit_pct",
                            limit,
                            scope=issuer,
                            unit="percent",
                            inputs=inputs,
                            evidence_ids=citations,
                        )
                    )
                single_issuer = any(
                    identifier in self.instruments.index
                    and self.instruments.loc[identifier, "asset_class"]
                    in {"Equity", "Fixed Income"}
                    for identifier in direct_members
                )
                hidden = single_issuer and direct == 0 and (direct + indirect) / total >= 0.1
                over_limit = limit is not None and (direct + indirect) / total * 100 > limit
                if over_limit or hidden:
                    context.emit_signal(
                        client_id,
                        "lookthrough_concentration",
                        "medium" if over_limit else "low",
                        scope=issuer,
                        fact_ids=[fact.id for fact in facts],
                        evidence_ids=citations,
                        threshold={
                            **inputs,
                            "limit_pct": limit,
                            "hidden_exposure_min_pct": 10,
                            "hidden_exposure": hidden,
                            "limit_exceeded": over_limit,
                            "action": "Review issuer exposure against each managed mandate",
                        },
                    )
            self._accumulators(client_id, household)

    def _unknown_baskets(self, client_id: str, household: pd.DataFrame, total: float) -> None:
        context = self.context
        products = household.loc[household["asset_class"].eq("Structured Products")]
        for instrument_id, positions in products.groupby("instrument_id"):
            mapping = self.lookthrough.get(instrument_id)
            missing = mapping.get("missing_underlyings", []) if mapping else ["Map unavailable"]
            if not missing:
                continue
            disclosure = mapping["disclosure"] if mapping else "No eligible reviewed product map"
            inputs = {
                **self.map_inputs(),
                "instrument_id": instrument_id,
                "missing_underlyings": missing,
                "disclosure": disclosure,
                "status": "Unscreenable constituents, not zero exposure",
                "market_value_usd": float(positions["market_value_usd"].sum()),
                "household_usd": total,
                "action": "Request complete basket constituents and term sheet",
            }
            self.missing_baskets.setdefault(client_id, []).append(inputs)
            citations = self.household_evidence(client_id) + [f"instruments:{instrument_id}"]
            fact = context.emit_fact(
                client_id,
                "concentration.unscreenable_product_pct",
                float(positions["market_value_usd"].sum()) / total * 100,
                scope=instrument_id,
                unit="percent",
                inputs=inputs,
                evidence_ids=citations,
            )
            context.emit_signal(
                client_id,
                "lookthrough_unavailable",
                "low",
                scope=instrument_id,
                fact_ids=[fact.id],
                evidence_ids=citations,
                threshold=inputs,
            )

    def _accumulators(self, client_id: str, household: pd.DataFrame) -> None:
        context = self.context
        for instrument_id in sorted(set(household["instrument_id"]) & self.lookthrough.keys()):
            mapping = self.lookthrough[instrument_id]
            if mapping["product_type"] != "daily accumulator":
                continue
            reference = str(self.instruments.loc[instrument_id, "underlying_reference"])
            strike_match = re.search(r"strike HKD ([0-9.]+)", reference)
            underlyings = mapping["underlying_ids"]
            price_column = f"price_{context.snapshot}"
            if not strike_match or len(underlyings) != 1 or price_column not in self.instruments:
                context.context_issues.append(f"{instrument_id}: accumulator terms unavailable")
                continue
            strike = float(strike_match[1])
            price = float(self.instruments.loc[underlyings[0], price_column])
            if strike <= 0 or pd.isna(price):
                continue
            inputs = {
                **self.map_inputs(),
                "strike_hkd": strike,
                "stock_price_hkd": price,
                "disclosure": mapping["disclosure"],
                "action": "Obtain remaining accumulation notional and double-up obligations",
            }
            citations = self.instrument_evidence({instrument_id})
            citations += context.holding_evidence(
                household.loc[household["instrument_id"].eq(instrument_id)]
            )
            fact = context.emit_fact(
                client_id,
                "concentration.accumulator_below_strike_pct",
                (1 - price / strike) * 100,
                scope=instrument_id,
                unit="percent",
                inputs=inputs,
                evidence_ids=citations,
            )
            if price < strike:
                context.emit_signal(
                    client_id,
                    "accumulator_forward_exposure",
                    "low",
                    scope=instrument_id,
                    fact_ids=[fact.id],
                    evidence_ids=citations,
                    threshold=inputs,
                )

    def collateral(self) -> None:
        context = self.context
        facilities = context.tables["credit_facilities"]
        unresolved = self.maps.get("unresolved_event_context", {})
        event_rows = context.tables["event_log"]
        eligible_events = event_rows.loc[
            event_rows["event_date"].isin(unresolved.get("supporting_event_dates", []))
            & event_rows["event_date"].le(context.asof.isoformat())
        ]
        unresolved_members = set().union(
            *(self.channel_instruments(channel) for channel in unresolved.get("channels", []))
        )
        for _, facility in facilities.iterrows():
            client_id = str(facility["client_id"])
            if client_id not in self.households:
                continue
            facility_id = str(facility["facility_id"])
            pledged = context.holdings.loc[
                context.holdings["portfolio_id"].eq(facility["collateral_portfolio_id"])
            ]
            rows = []
            citations = [evidence_id("credit_facilities", facility)]
            for snapshot, positions in pledged.groupby("snapshot_date", sort=True):
                drawn_field = f"drawn_{snapshot}"
                if drawn_field not in facility or pd.isna(facility[drawn_field]):
                    continue
                components = {}
                try:
                    for position in positions.itertuples():
                        lending = context.to_usd(
                            position.market_value_base * position.advance_rate_pct / 100,
                            position.portfolio_ccy,
                            snapshot,
                        ) / context.to_usd(1, str(facility["facility_ccy"]), snapshot)
                        components[position.instrument_id] = lending
                        citations.extend(context.fx_evidence(position.portfolio_ccy, snapshot))
                    citations.extend(context.fx_evidence(str(facility["facility_ccy"]), snapshot))
                except ValueError as error:
                    context.context_issues.append(f"{facility_id}: collateral unavailable: {error}")
                    continue
                lending_value = sum(components.values())
                if lending_value <= 0:
                    context.context_issues.append(f"{facility_id}: non-positive lending value")
                    continue
                citations.extend(context.holding_evidence(positions))
                rows.append(
                    {
                        "snapshot": str(snapshot),
                        "drawn": float(facility[drawn_field]),
                        "lending_value": lending_value,
                        "components": components,
                        "ltv": float(facility[drawn_field]) / lending_value * 100,
                    }
                )
            if not rows or rows[-1]["snapshot"] != context.snapshot:
                continue
            trigger = float(facility["margin_call_ltv_pct"])
            current = rows[-1]
            headroom = trigger - current["ltv"]
            increases = 0
            for earlier, later in reversed(list(pairwise(rows))):
                if later["ltv"] <= earlier["ltv"]:
                    break
                increases += 1
            breaches = [index for index, row in enumerate(rows) if row["ltv"] > trigger]
            fragile = False
            recovery_share = 0.0
            recovery_evaluated = False
            cure_without_repayment = False
            if breaches and current["ltv"] <= trigger and not eligible_events.empty:
                recovery_evaluated = True
                breached = rows[breaches[-1]]
                subsequent = rows[breaches[-1] :]
                cure_without_repayment = all(
                    later["drawn"] >= earlier["drawn"] - 0.01
                    for earlier, later in pairwise(subsequent)
                )
                recovery = {
                    instrument: max(
                        0.0,
                        current["components"].get(instrument, 0)
                        - breached["components"].get(instrument, 0),
                    )
                    for instrument in current["components"].keys() | breached["components"].keys()
                }
                recovery_total = sum(recovery.values())
                if recovery_total > 0:
                    recovery_share = (
                        sum(
                            value
                            for instrument, value in recovery.items()
                            if instrument in unresolved_members
                        )
                        / recovery_total
                        * 100
                    )
                fragile = cure_without_repayment and recovery_total > 0 and recovery_share >= 50
                if fragile:
                    citations.extend(context.evidence("event_log", eligible_events))
                    citations.extend(self.instrument_evidence(unresolved_members))
            inputs = {
                **self.map_inputs(),
                "facility_id": facility_id,
                "facility_ccy": str(facility["facility_ccy"]),
                "history": rows,
                "margin_call_ltv_pct": trigger,
                "breach_dates": [rows[index]["snapshot"] for index in breaches],
                "cure_without_drawn_reduction": cure_without_repayment,
                "fragile_cure": fragile,
                "recovery_share_available": recovery_evaluated,
                "disclosure": (
                    "LTV uses haircut lending value; fragile cure is not a reopening loss forecast"
                ),
            }
            measurements = [
                ("ltv_pct", current["ltv"], "percent"),
                ("headroom_pp", headroom, "percentage_points"),
                ("consecutive_increases", increases, "number"),
                ("lending_value", current["lending_value"], "currency"),
            ]
            if recovery_evaluated:
                measurements.append(("unresolved_recovery_share_pct", recovery_share, "percent"))
            facts = [
                context.emit_fact(
                    client_id,
                    f"collateral.{kind}",
                    value,
                    scope=facility_id,
                    unit=unit,
                    currency=str(facility["facility_ccy"]) if unit == "currency" else None,
                    inputs=inputs,
                    evidence_ids=citations,
                )
                for kind, value, unit in measurements
            ]
            if current["ltv"] > trigger or headroom <= 5 or increases >= 3 or fragile:
                context.emit_signal(
                    client_id,
                    "collateral_stress",
                    "high" if current["ltv"] > trigger else "medium",
                    scope=facility_id,
                    fact_ids=[fact.id for fact in facts],
                    evidence_ids=citations,
                    threshold={
                        **inputs,
                        "proximity_pp": 5,
                        "consecutive_increases_min": 3,
                        "fragile_cure_recovery_min_pct": 50,
                        "action": "Review collateral, repayment and linked funding obligations",
                    },
                )

    def currency(self) -> None:
        context = self.context
        horizon = pd.Timestamp(context.asof) + pd.DateOffset(months=24)
        needs = context.tables["planned_cash_needs"]
        for client in context.clients.itertuples():
            client_id = client.client_id
            if client_id not in self.households or self.totals[client_id] <= 0:
                continue
            household = self.households[client_id]
            non_base = float(
                household.loc[
                    household["instrument_ccy"].ne(client.base_currency), "market_value_usd"
                ].sum()
            )
            percentage = non_base / float(self.totals[client_id]) * 100
            confirmed = needs.loc[
                needs["client_id"].eq(client_id)
                & needs["certainty"].eq("Confirmed")
                & needs["currency"].eq(client.base_currency)
                & pd.to_datetime(needs["due_from"]).le(horizon)
                & pd.to_datetime(needs["due_to"]).ge(pd.Timestamp(context.asof))
            ]
            objective = self.qualified_override("currency_objective_overrides", client_id)
            objective_qualified = objective.get(
                "currency"
            ) == client.base_currency and not objective.get("currency_inferred", False)
            citations = self.household_evidence(client_id) + [f"clients:{client_id}"]
            citations += context.evidence("planned_cash_needs", confirmed)
            if objective_qualified:
                citations += objective["evidence_ids"]
            inputs = {
                **self.map_inputs(),
                "base_currency": client.base_currency,
                "non_base_market_value_usd": non_base,
                "household_usd": float(self.totals[client_id]),
                "confirmed_base_need_ids": confirmed["need_id"].tolist(),
                "base_currency_income_objective": objective if objective_qualified else None,
                "disclosure": (
                    "Assumed unhedged; denomination is not full fund currency look-through"
                ),
            }
            fact = context.emit_fact(
                client_id,
                "currency.non_base_pct",
                percentage,
                unit="percent",
                inputs=inputs,
                evidence_ids=citations,
            )
            if percentage > 40:
                context.emit_signal(
                    client_id,
                    "currency_mismatch",
                    "high" if not confirmed.empty or objective_qualified else "low",
                    fact_ids=[fact.id],
                    evidence_ids=citations,
                    threshold={**inputs, "non_base_pct_gt": 40, "need_horizon_months": 24},
                )

    def events(self) -> None:
        context = self.context
        if not self.maps:
            context.context_issues.append(
                "Event transmission maps unavailable before effective date"
            )
            return
        events = context.tables["event_log"]
        for _, event in events.iterrows():
            if str(event["event_date"]) > context.asof.isoformat():
                continue
            mapping = self.maps["transmission_map"].get(event["primary_transmission"])
            if mapping is None:
                context.context_issues.append(
                    f"Unmapped event transmission: {event['primary_transmission']}; review map"
                )
                continue
            event_id = evidence_id("event_log", event)
            for channel in mapping["channels"]:
                members = self.channel_instruments(channel)
                definition = self.maps["channels"][channel]
                for client_id, household in self.households.items():
                    total = float(self.totals[client_id])
                    exposed = household.loc[household["instrument_id"].isin(members)]
                    numerator = float(exposed["market_value_usd"].sum())
                    if numerator <= 0 or total <= 0:
                        continue
                    percentage = numerator / total * 100
                    wealth = self.qualified_override("wealth_channel_overrides", client_id)
                    overlaps = channel in wealth.get("channels", [])
                    citations = [event_id, f"clients:{client_id}"]
                    citations += self.household_evidence(client_id)
                    citations += self.instrument_evidence(set(exposed["instrument_id"]))
                    if overlaps:
                        citations += wealth["evidence_ids"]
                    inputs = {
                        **self.map_inputs(),
                        "event_evidence_id": event_id,
                        "primary_transmission": str(event["primary_transmission"]),
                        "channel": channel,
                        "scenario": definition["scenario"],
                        "direction": definition["direction"],
                        "wealth_correlation": overlaps,
                        "wealth_overlap_basis": wealth.get("basis") if overlaps else None,
                        "channel_market_value_usd": numerator,
                        "household_usd": total,
                        "disclosures": [definition["disclosure"], *mapping["unmapped_components"]],
                        "incomplete_lookthrough": self.missing_baskets.get(client_id, []),
                        "non_additive_across_channels": True,
                    }
                    scope = f"{event_id}:{channel}"
                    fact = context.emit_fact(
                        client_id,
                        "event.channel_exposure_pct",
                        percentage,
                        scope=scope,
                        unit="percent",
                        inputs=inputs,
                        evidence_ids=citations,
                    )
                    if percentage > 15:
                        context.emit_signal(
                            client_id,
                            "event_exposure",
                            "high" if overlaps else "medium",
                            scope=scope,
                            fact_ids=[fact.id],
                            evidence_ids=citations,
                            threshold={**inputs, "channel_exposure_pct_gt": 15},
                        )

    def suitability(self) -> None:
        context = self.context
        transactions = context.tables["transactions"]
        for client in context.clients.itertuples():
            client_id = client.client_id
            if client_id not in context.performance.index:
                continue
            metrics = context.performance.loc[client_id]
            period_return = metrics.get("return_base_ccy_pct")
            drawdown = metrics.get("snapshot_max_drawdown_pct")
            if pd.isna(period_return) or pd.isna(drawdown):
                continue
            history = context.holdings.loc[context.holdings["client_id"].eq(client_id)]
            income_rows = transactions.loc[
                transactions["client_id"].eq(client_id)
                & transactions["transaction_type"].isin(
                    [
                        "Dividend",
                        "Coupon",
                        "Interest",
                        "Distribution",
                        "Management Fee",
                    ]
                )
            ]
            citations = [f"clients:{client_id}"] + context.holding_evidence(history)
            citations += context.evidence("transactions", income_rows)
            try:
                for currency in {client.base_currency, *income_rows["currency"]}:
                    citations.extend(context.fx_evidence(currency))
            except ValueError as error:
                context.context_issues.append(
                    f"{client_id}: suitability income FX unavailable: {error}"
                )
                continue
            if client_id not in context.income_summary.index:
                continue
            income = context.income_summary.loc[client_id]
            if pd.isna(income.get("income_base")) or pd.isna(income.get("fees_base")):
                continue
            inputs = {
                "snapshot_date": context.snapshot,
                "baseline": context.baseline,
                "risk_tolerance_score": int(client.risk_tolerance_score),
                "base_currency": client.base_currency,
                "income_received_base": float(income["income_base"]),
                "fees_paid_base": float(income["fees_base"]),
                "disclosure": (
                    "Same-store price return; drawdown at available snapshots only, "
                    "not continuous volatility. Income and fees not reconciled to positions; "
                    "not total return."
                ),
            }
            facts = [
                context.emit_fact(
                    client_id,
                    f"suitability.{kind}",
                    float(value),
                    unit=unit,
                    currency=client.base_currency if unit == "currency" else None,
                    inputs=inputs,
                    evidence_ids=citations,
                )
                for kind, value, unit in [
                    ("period_return_pct", period_return, "percent"),
                    ("snapshot_drawdown_pct", drawdown, "percent"),
                    ("income_received_base", income["income_base"], "currency"),
                    ("fees_paid_base", income["fees_base"], "currency"),
                ]
            ]
            if client.risk_tolerance_score <= 3 and (period_return < -5 or drawdown < -7):
                context.emit_signal(
                    client_id,
                    "suitability_drift",
                    "medium",
                    fact_ids=[fact.id for fact in facts],
                    evidence_ids=citations,
                    threshold={
                        **inputs,
                        "risk_tolerance_max": 3,
                        "period_return_pct_lt": -5,
                        "snapshot_drawdown_pct_lt": -7,
                    },
                )
