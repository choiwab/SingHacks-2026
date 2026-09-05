"""Canonical funding obligations, cash tiers and reviewed deadline escalation rules."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from app.analytics.phase_a import PhaseAContext

NEED_COMMITMENT_LINKS = {"CN-016": ("COM-001", "COM-002"), "CN-008": ("COM-003",)}
CERTAINTIES = {"Confirmed", "Likely", "Conditional on the sale completing", "Aspirational"}
FUNDING_DISCLOSURE = (
    "Cash and short-term deposits support the 12-month test; only Daily cash supports the "
    "near-term test. Daily-liquid securities are gross resources before encumbrance, settlement, "
    "disposal costs, tax and FX confirmation. Not a solvency finding."
)
OBLIGATION_CONVENTION = (
    "Confirmed/Likely needs count fully, once per 12-month window. Annual instalment amounts "
    "use the full stated planning amount, since the payment schedule is unavailable. Active "
    "recurring needs with past start dates remain active. Overlapping call windows include the "
    "entire uncalled balance as a stress reserve, not a forecast of actual calls."
)


def parse_call_window(window: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start, end = window.split(" to ")
    return (
        pd.Period(start.replace(" ", ""), freq="Q").start_time.normalize(),
        pd.Period(end.replace(" ", ""), freq="Q").end_time.normalize(),
    )


def funding_severity(
    cash_cover: float | None, daily_cover: float | None, near_term_need: float, daily_cash: float
) -> str:
    near_term_shortfall = near_term_need > 0 and daily_cash < near_term_need
    cash_shortfall = cash_cover is not None and cash_cover < 1.0
    insufficient_daily = daily_cover is not None and daily_cover < 1.5
    if near_term_shortfall or cash_shortfall and insufficient_daily:
        return "high"
    return "medium" if cash_shortfall else "none"


def _validated_links(context: PhaseAContext) -> dict[str, tuple[str, ...]]:
    needs = context.tables["planned_cash_needs"].set_index("need_id")
    commitments = context.tables["commitments"].set_index("commitment_id")
    links = {}
    for need_id, commitment_ids in NEED_COMMITMENT_LINKS.items():
        if need_id not in needs.index:
            continue
        present = set(commitment_ids).intersection(commitments.index)
        if not present:
            continue
        if present != set(commitment_ids):
            raise ValueError(f"DQ-11 incomplete commitment restatement for {need_id}")
        need = needs.loc[need_id]
        calls = commitments.loc[list(commitment_ids)]
        windows = [parse_call_window(window) for window in calls["expected_call_window"]]
        valid = (
            calls["client_id"].eq(need["client_id"]).all()
            and calls["currency"].eq(need["currency"]).all()
            and math.isclose(
                float(calls["uncalled"].sum()), float(need["amount"]), abs_tol=0.01, rel_tol=0
            )
            and min(window[0] for window in windows) == pd.Timestamp(need["due_from"])
            and max(window[1] for window in windows) == pd.Timestamp(need["due_to"])
        )
        if not valid:
            raise ValueError(f"DQ-11 restatement mismatch for {need_id}; identity requires review")
        links[need_id] = commitment_ids
    return links


def _client_obligations(context: PhaseAContext, client_id: str, links: dict) -> tuple[list, list]:
    start = pd.Timestamp(context.asof)
    horizon = start + pd.DateOffset(months=12)
    needs = context.tables["planned_cash_needs"]
    calls = context.tables["commitments"]
    client_needs = needs.loc[needs["client_id"].eq(client_id)]
    client_calls = calls.loc[calls["client_id"].eq(client_id)]
    obligations, contingencies = [], []
    for need in client_needs.itertuples():
        if need.certainty not in CERTAINTIES:
            raise ValueError(f"Unknown certainty {need.certainty!r} for {need.need_id}")
        if pd.Timestamp(need.due_from) > horizon or pd.Timestamp(need.due_to) < start:
            continue
        if need.certainty == "Aspirational" or need.need_id in links:
            continue
        row = {
            "obligation_id": need.need_id,
            "source_kind": "planned_cash_need",
            "amount_usd": context.to_usd(need.amount, need.currency),
            "certainty": need.certainty,
            "due_from": need.due_from,
            "due_to": need.due_to,
            "confirmed_planned_need": need.certainty == "Confirmed",
            "evidence_ids": [f"planned_cash_needs:{need.need_id}"]
            + context.fx_evidence(need.currency),
        }
        if need.certainty == "Conditional on the sale completing":
            row["dependency"] = (
                "Sale completion generates liquidity; proceeds unverified and excluded"
            )
            contingencies.append(row)
        else:
            obligations.append(row)
    for call in client_calls.itertuples():
        call_start, call_end = parse_call_window(call.expected_call_window)
        if call_start > horizon or call_end < start:
            continue
        linked_ids = [need_id for need_id, ids in links.items() if call.commitment_id in ids]
        matched_needs = needs.loc[needs["need_id"].isin(linked_ids)]
        obligations.append(
            {
                "obligation_id": call.commitment_id,
                "source_kind": "uncalled_commitment",
                "amount_usd": context.to_usd(call.uncalled, call.currency),
                "certainty": "Contractual uncalled balance; call timing uncertain",
                "due_from": call_start.date().isoformat(),
                "due_to": call_end.date().isoformat(),
                "confirmed_planned_need": bool(matched_needs["certainty"].eq("Confirmed").any()),
                "evidence_ids": [f"commitments:{call.commitment_id}"]
                + [f"planned_cash_needs:{need_id}" for need_id in linked_ids]
                + context.fx_evidence(call.currency),
            }
        )
    return obligations, contingencies


def _withdrawal_scenario(context: PhaseAContext, client_id: str) -> dict:
    if client_id != "CL-0003" or not context.reference_maps:
        return {}
    needs = context.tables["planned_cash_needs"]
    needs = needs.loc[needs["need_id"].eq("CN-004") & needs["client_id"].eq(client_id)]
    portfolios = context.portfolios.loc[
        context.portfolios["portfolio_id"].eq("PF-0005")
        & context.portfolios["client_id"].eq(client_id)
        & context.portfolios["service_model"].ne("Custody")
    ]
    if len(needs) != 1 or len(portfolios) != 1:
        return {}
    need, portfolio = needs.iloc[0], portfolios.iloc[0]
    if need["certainty"] != "Confirmed" or pd.Timestamp(need["due_to"]) < pd.Timestamp(
        context.asof
    ):
        return {}
    holdings = context.latest.loc[context.latest["portfolio_id"].eq(portfolio["portfolio_id"])]
    if holdings.empty or not holdings["portfolio_ccy"].eq(need["currency"]).all():
        return {}
    rules = context.mandates.loc[
        context.mandates["mandate_code"].eq(portfolio["mandate_code"])
        & context.mandates["asset_class"].isin(["Equity", "Fixed Income"])
    ]
    if len(rules) != 2 or rules["asset_class"].nunique() != 2:
        return {}
    total = float(holdings["market_value_base"].sum())
    equity = float(holdings.loc[holdings["asset_class"].eq("Equity"), "market_value_base"].sum())
    fixed_income = float(
        holdings.loc[holdings["asset_class"].eq("Fixed Income"), "market_value_base"].sum()
    )
    withdrawal = float(need["amount"])
    if withdrawal <= 0 or withdrawal >= total or withdrawal > equity:
        context.context_issues.append("PF-0005 equity-funded withdrawal scenario is infeasible.")
        return {}
    maximum = float(rules.set_index("asset_class").loc["Equity", "max_pct"])
    post_total, post_equity = total - withdrawal, equity - withdrawal
    further_shift = max(post_equity - post_total * maximum / 100, 0.0)
    evidence = context.holding_evidence(holdings) + context.evidence("mandates", rules)
    evidence += ["planned_cash_needs:CN-004", "portfolios:PF-0005"]
    if "N-005" in context.notes:
        evidence.append("rm_notes:N-005")
    metadata = {
        "portfolio_id": "PF-0005",
        "need_id": "CN-004",
        "snapshot": context.snapshot,
        "scenario": "Sell Equity, pay the need externally, then reallocate Equity to Fixed Income",
        "disclosure": (
            "Illustration, not a trade instruction. Assumes unchanged prices, no execution costs, "
            "no additional disposal tax and no other flows. Does not establish every Mandate "
            "rule is cured. Re-solicit the no-change instruction and confirm the funding plan. "
            "Obtain original tax-lot history; transfer book bases do not support "
            "disposal-tax advice."
        ),
    }
    measurements = {
        "withdrawal_base": (withdrawal, "currency"),
        "post_withdrawal_total_base": (post_total, "currency"),
        "post_withdrawal_equity_pct": (post_equity / post_total * 100, "percent"),
        "further_equity_reallocation_base": (further_shift, "currency"),
        "post_reallocation_equity_pct": (
            (post_equity - further_shift) / post_total * 100,
            "percent",
        ),
        "post_reallocation_fixed_income_pct": (
            (fixed_income + further_shift) / post_total * 100,
            "percent",
        ),
    }
    return {
        kind: context.emit_fact(
            client_id,
            f"funding.scenario.{kind}",
            amount,
            scope="PF-0005:CN-004",
            unit=unit,
            currency=need["currency"] if unit == "currency" else None,
            evidence_ids=evidence,
            inputs=metadata,
        )
        for kind, (amount, unit) in measurements.items()
    }


def compute_funding(context: PhaseAContext) -> None:
    links = _validated_links(context)
    rows = []
    near_end = pd.Timestamp(context.asof) + pd.DateOffset(months=6)
    for client_id in context.client_names:
        holdings = context.latest.loc[context.latest["client_id"].eq(client_id)]
        if holdings.empty:
            continue
        cash = holdings["asset_class"].eq("Cash and Equivalents")
        daily = holdings["liquidity_tier"].eq("Daily")
        amounts = {
            "cash_usd": float(holdings.loc[cash, "market_value_usd"].sum()),
            "daily_cash_usd": float(holdings.loc[cash & daily, "market_value_usd"].sum()),
            "term_deposits_usd": float(holdings.loc[cash & ~daily, "market_value_usd"].sum()),
            "daily_usd": float(holdings.loc[daily, "market_value_usd"].sum()),
            "locked_usd": float(holdings.loc[~daily, "market_value_usd"].sum()),
        }
        source_evidence = context.holding_evidence(holdings)
        emitted = {}
        for kind, amount in amounts.items():
            emitted[kind] = context.emit_fact(
                client_id,
                f"funding.{kind}",
                amount,
                unit="currency",
                currency="USD",
                evidence_ids=source_evidence,
                inputs={"snapshot": context.snapshot, "disclosure": FUNDING_DISCLOSURE},
            )
        historical_calls = context.tables["commitments"].loc[
            context.tables["commitments"]["client_id"].eq(client_id)
        ]
        if context.asof < context.reference_effective_date and not historical_calls.empty:
            context.context_issues.append(
                f"{client_id}: historical uncalled balances unavailable; current called-to-date "
                "cannot reconstruct history. Funding obligations, covers and Signals withheld."
            )
            rows.append({"client_id": client_id, **amounts, "severity": "unavailable"})
            continue
        try:
            obligations, contingencies = _client_obligations(context, client_id, links)
        except ValueError as error:
            if "FX" not in str(error):
                raise
            context.context_issues.append(f"{client_id}: funding amounts unavailable: {error}")
            rows.append({"client_id": client_id, **amounts, "severity": "unavailable"})
            continue
        near = [
            row
            for row in obligations
            if row["confirmed_planned_need"] and pd.Timestamp(row["due_from"]) <= near_end
        ]
        obligations_usd = sum(row["amount_usd"] for row in obligations)
        near_usd = sum(row["amount_usd"] for row in near)
        evidence = (
            source_evidence
            + [identifier for row in obligations for identifier in row["evidence_ids"]]
            + [f"clients:{client_id}"]
        )
        metadata = {
            "snapshot": context.snapshot,
            "horizon_start": context.asof.isoformat(),
            "horizon_months": 12,
            "near_term_months": 6,
            "obligations": obligations,
            "certainty_convention": OBLIGATION_CONVENTION,
            "disclosure": FUNDING_DISCLOSURE,
            "dedup_links": {
                need_id: list(ids)
                for need_id, ids in links.items()
                if any(row["obligation_id"] in ids for row in obligations)
            },
        }
        measurements = {
            "obligations_usd": obligations_usd,
            "confirmed_near_term_usd": near_usd,
            "needs_12m_usd": sum(
                row["amount_usd"]
                for row in obligations
                if row["source_kind"] == "planned_cash_need"
            ),
            "uncalled_usd": sum(
                row["amount_usd"]
                for row in obligations
                if row["source_kind"] == "uncalled_commitment"
            ),
        }
        for kind, amount in measurements.items():
            emitted[kind] = context.emit_fact(
                client_id,
                f"funding.{kind}",
                amount,
                unit="currency",
                currency="USD",
                evidence_ids=evidence,
                inputs=metadata,
            )
        for contingency in contingencies:
            context.emit_fact(
                client_id,
                "funding.contingent_need_usd",
                contingency["amount_usd"],
                scope=contingency["obligation_id"],
                unit="currency",
                currency="USD",
                evidence_ids=contingency["evidence_ids"],
                inputs={**contingency, "excluded_from_baseline": True},
            )
        cash_cover = amounts["cash_usd"] / obligations_usd if obligations_usd > 0 else None
        daily_cover = amounts["daily_usd"] / obligations_usd if obligations_usd > 0 else None
        near_cover = amounts["daily_cash_usd"] / near_usd if near_usd > 0 else None
        ratios = {
            "cash_cover_x": cash_cover,
            "daily_cover_x": daily_cover,
            "daily_cash_near_term_cover_x": near_cover,
        }
        for kind, ratio in ratios.items():
            if ratio is not None:
                emitted[kind] = context.emit_fact(
                    client_id,
                    f"funding.{kind}",
                    ratio,
                    unit="ratio",
                    inputs=metadata,
                    evidence_ids=evidence,
                )
        severity = funding_severity(cash_cover, daily_cover, near_usd, amounts["daily_cash_usd"])
        emitted.update(_withdrawal_scenario(context, client_id))
        twelve_month_escalation = (
            cash_cover is not None
            and cash_cover < 1
            and daily_cover is not None
            and daily_cover < 1.5
        )
        near_escalation = near_usd > amounts["daily_cash_usd"]
        if severity != "none":
            context.emit_signal(
                client_id,
                "funding_gap",
                severity,
                fact_ids=[fact.id for fact in emitted.values()],
                threshold={
                    **metadata,
                    "cash_warn_below_x": 1.0,
                    "daily_escalate_below_x": 1.5,
                    "escalate_12m": twelve_month_escalation,
                    "escalate_near_term": near_escalation,
                    "rule": "cash <1 AND Daily <1.5, OR confirmed6m exceeds Daily cash",
                },
            )
        rows.append(
            {
                "client_id": client_id,
                **amounts,
                **measurements,
                **ratios,
                "severity": severity,
                "escalate_12m": twelve_month_escalation,
                "escalate_near_term": near_escalation,
            }
        )
    context.liquidity = pd.DataFrame(rows).set_index("client_id") if rows else pd.DataFrame()
