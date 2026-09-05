"""Reported-mark performance and separate, unreconciled transaction receipts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from app.analytics.phase_a import PhaseAContext

INCOME_TYPES = ("Dividend", "Coupon", "Interest", "Distribution")
PURCHASE_TYPES = ("Buy", "Structured Product Subscription")
KEYS = ["portfolio_id", "instrument_id"]
PERFORMANCE_DISCLOSURE = (
    "Same-store reported-mark comparison; excludes added positions and their own moves since "
    "purchase. Five or fewer snapshots, potentially stale marks; not reconciled total return."
)
INCOME_DISCLOSURE = (
    "Not reconciled to positions; translated at latest observed snapshot FX, not trade-date FX. "
    "Gross household receipts, management fees and financing interest are separate measures."
)


def _income(context: PhaseAContext) -> None:
    transactions = context.tables["transactions"]
    summary_columns = [
        f"{measure}_{currency}"
        for measure in ("income", "fees", "financing_interest")
        for currency in ("usd", "base")
    ]
    context.income_summary = pd.DataFrame(
        index=list(context.client_names), columns=summary_columns, dtype=float
    )
    if transactions.empty:
        context.context_issues.append(
            "Income and fees unavailable: no eligible transaction ledger was supplied."
        )
        return
    eligible = transactions.loc[
        transactions["trade_date"].between(context.baseline, context.snapshot)
        & transactions["settlement_date"].le(context.snapshot)
    ]
    measures = {
        "income": (INCOME_TYPES, 1, "income.received"),
        "fees": (("Management Fee",), -1, "fees.management"),
        "financing_interest": (("Interest Charge",), -1, "fees.financing_interest"),
    }
    for client_id in context.client_names:
        client_rows = eligible.loc[eligible["client_id"].eq(client_id)].copy()
        if client_rows.empty:
            context.context_issues.append(
                f"{client_id}: income/fees unavailable: no eligible transaction ledger rows."
            )
            continue
        base = context.base_ccy[client_id]
        try:
            client_rows["amount_usd"] = [
                context.to_usd(row.amount, row.currency) for row in client_rows.itertuples()
            ]
            client_rows["amount_base"] = client_rows["amount_usd"] / context.to_usd(1, base)
            conversion = sorted(
                {
                    identifier
                    for currency in {*client_rows["currency"], base}
                    for identifier in context.fx_evidence(currency)
                }
            )
        except ValueError as error:
            context.context_issues.append(f"{client_id}: income/fees unavailable: {error}")
            continue
        for measure, (types, sign, kind) in measures.items():
            selected = client_rows.loc[client_rows["transaction_type"].isin(types)]
            evidence = context.evidence("transactions", selected) + conversion
            if selected.empty:
                evidence += context.evidence("transactions", client_rows)
            evidence.append(f"clients:{client_id}")
            for currency_measure, currency in (("usd", "USD"), ("base", base)):
                amount = float(sign * selected[f"amount_{currency_measure}"].sum())
                context.income_summary.loc[client_id, f"{measure}_{currency_measure}"] = amount
                context.emit_fact(
                    client_id,
                    f"{kind}_{currency_measure}",
                    amount,
                    unit="currency",
                    currency=currency,
                    evidence_ids=evidence,
                    inputs={
                        "transaction_types": list(types),
                        "period_start": context.baseline,
                        "period_end": context.snapshot,
                        "fx_snapshot": context.snapshot,
                        "disclosure": INCOME_DISCLOSURE,
                    },
                )


def _decomposition(
    context: PhaseAContext,
    client_id: str,
    opening: pd.DataFrame,
    ending: pd.DataFrame,
    evidence: list[str],
) -> None:
    joined = opening.set_index(KEYS).join(
        ending.set_index(KEYS), how="outer", lsuffix="_start", rsuffix="_end"
    )
    if joined["quantity_end"].isna().any():
        context.context_issues.append(f"{client_id}: disposals prevent added-unit decomposition.")
        return
    added = joined["quantity_end"] - joined["quantity_start"].fillna(0)
    if added.lt(0).any():
        context.context_issues.append(f"{client_id}: reduced quantities need lot/flow attribution.")
        return
    transactions = context.tables["transactions"]
    purchases = transactions.loc[
        transactions["client_id"].eq(client_id)
        & transactions["transaction_type"].isin(PURCHASE_TYPES)
        & transactions["trade_date"].gt(context.baseline)
        & transactions["trade_date"].le(context.snapshot)
        & transactions["settlement_date"].le(context.snapshot)
    ].copy()
    quantities = purchases.groupby(KEYS)["quantity"].sum()
    additions = added.loc[added.gt(0)]
    if set(quantities.index) != set(additions.index) or not np.allclose(
        quantities.reindex(additions.index), additions, atol=1e-8, rtol=0
    ):
        context.context_issues.append(
            f"{client_id}: additions do not match settled purchases; cost/own-move withheld."
        )
        return
    try:
        cost = sum(-context.to_usd(row.amount, row.currency) for row in purchases.itertuples())
        fx_evidence = [
            identifier
            for currency in purchases["currency"].unique()
            for identifier in context.fx_evidence(currency)
        ]
    except ValueError as error:
        context.context_issues.append(f"{client_id}: purchase attribution unavailable: {error}")
        return
    if purchases["amount"].ge(0).any():
        context.context_issues.append(f"{client_id}: purchase costs are not signed cash outflows.")
        return
    original_quantity = joined["quantity_start"].fillna(0)
    start_fx = joined["market_value_usd_start"] / joined["market_value_local_start"]
    end_fx = joined["market_value_usd_end"] / joined["market_value_local_end"]
    start_fx = start_fx.fillna(end_fx)
    start_price = joined["price_local_start"].fillna(joined["price_local_end"])
    price_move = (original_quantity * (joined["price_local_end"] - start_price) * start_fx).sum()
    fx_move = (original_quantity * joined["price_local_end"] * (end_fx - start_fx)).sum()
    addition_end = (added * joined["price_local_end"] * end_fx).sum()
    value_change = ending["market_value_usd"].sum() - opening["market_value_usd"].sum()
    if not np.isclose(price_move + fx_move + addition_end, value_change, atol=0.05, rtol=1e-9):
        context.context_issues.append(f"{client_id}: price/FX decomposition does not reconcile.")
        return
    measures = {
        "starting_price_effect_usd": price_move,
        "starting_fx_effect_usd": fx_move,
        "new_position_cost_usd": cost,
        "added_position_end_value_usd": addition_end,
        "post_purchase_move_usd": addition_end - cost,
    }
    for kind, value in measures.items():
        context.emit_fact(
            client_id,
            f"performance.{kind}",
            value,
            unit="currency",
            currency="USD",
            evidence_ids=evidence + context.evidence("transactions", purchases) + fx_evidence,
            inputs={
                "baseline": context.baseline,
                "snapshot": context.snapshot,
                "purchase_fx_basis": "current snapshot FX; trade-date FX unavailable",
                "disclosure": PERFORMANCE_DISCLOSURE,
            },
        )


def compute_performance(context: PhaseAContext) -> None:
    _income(context)
    context.performance = pd.DataFrame(
        index=list(context.client_names),
        columns=["return_base_ccy_pct", "return_usd_pct", "snapshot_max_drawdown_pct"],
        dtype=float,
    )
    series_by_client = {}
    for client_id in context.client_names:
        history = context.holdings.loc[context.holdings["client_id"].eq(client_id)].copy()
        opening = history.loc[history["snapshot_date"].eq(context.baseline)]
        ending = history.loc[history["snapshot_date"].eq(context.snapshot)]
        if opening.empty or ending.empty:
            context.context_issues.append(
                f"{client_id}: a complete opening/ending snapshot is missing."
            )
            continue
        evidence = context.holding_evidence(history)
        context.emit_fact(
            client_id,
            "portfolio.total_usd",
            ending["market_value_usd"].sum(),
            unit="currency",
            currency="USD",
            evidence_ids=context.holding_evidence(ending),
            inputs={
                "snapshot": context.snapshot,
                "basis": "reported holdings, including stale marks",
            },
        )
        baseline_quantity = opening.set_index(KEYS)["quantity"]
        keyed = history.set_index(KEYS)
        keyed["baseline_quantity"] = baseline_quantity.reindex(keyed.index).fillna(0)
        missing_opening_positions = any(
            not set(baseline_quantity.index).issubset(set(frame.set_index(KEYS).index))
            for _, frame in history.groupby("snapshot_date")
        )
        if (
            missing_opening_positions
            or keyed["quantity"].le(0).any()
            or (keyed["quantity"] < keyed["baseline_quantity"]).any()
        ):
            context.context_issues.append(
                f"{client_id}: disposals/missing positions prevent comparable baseline quantities."
            )
            continue
        if not history["portfolio_ccy"].eq(context.base_ccy[client_id]).all():
            context.context_issues.append(f"{client_id}: mixed base currencies need translation.")
            continue
        series = {}
        for measure in ("usd", "base"):
            values = (
                keyed[f"market_value_{measure}"] * keyed["baseline_quantity"] / keyed["quantity"]
            )
            series[measure] = values.groupby(keyed["snapshot_date"]).sum().sort_index()
            if series[measure].iloc[0] <= 0:
                raise ValueError(f"Non-positive starting value for {client_id}")
            result = 100 * (series[measure].iloc[-1] / series[measure].iloc[0] - 1)
            column = "return_usd_pct" if measure == "usd" else "return_base_ccy_pct"
            context.performance.loc[client_id, column] = result
            context.emit_fact(
                client_id,
                f"performance.same_store_return_{measure}_pct",
                result,
                unit="percent",
                evidence_ids=evidence,
                inputs={
                    "baseline": context.baseline,
                    "snapshot": context.snapshot,
                    "reporting_currency": "USD"
                    if measure == "usd"
                    else context.base_ccy[client_id],
                    "disclosure": PERFORMANCE_DISCLOSURE,
                },
            )
        drawdown = float((series["base"] / series["base"].cummax() - 1).min() * 100)
        context.performance.loc[client_id, "snapshot_max_drawdown_pct"] = drawdown
        series_by_client[client_id] = series["base"]
        context.emit_fact(
            client_id,
            "performance.snapshot_max_drawdown_pct",
            drawdown,
            unit="percent",
            evidence_ids=evidence,
            inputs={"disclosure": PERFORMANCE_DISCLOSURE},
        )
        _decomposition(context, client_id, opening, ending, evidence)
    context.same_store_base_values = pd.DataFrame.from_dict(series_by_client, orient="index")
