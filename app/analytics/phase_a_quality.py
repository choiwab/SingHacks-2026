"""Source-backed financial limitations that survive structural validation."""

from __future__ import annotations

import math

import pandas as pd

from app.pipeline.evidence import evidence_id
from app.pipeline.schemas import DataQualityFinding
from app.pipeline.stages.clean import CleanedSources


def phase_a_quality_findings(sources: CleanedSources) -> list[DataQualityFinding]:
    """Disclose incomplete accounting without inventing missing balances or tax lots."""
    findings: list[DataQualityFinding] = []
    cutoff = sources.as_of.isoformat()
    tables = sources.tables
    holdings = tables["holdings"].loc[tables["holdings"]["snapshot_date"].le(cutoff)]
    transactions = tables["transactions"].loc[
        tables["transactions"]["trade_date"].le(cutoff)
        & tables["transactions"]["settlement_date"].le(cutoff)
    ]

    def append(code, message, references, client_id=None, portfolio_id=None):
        findings.append(
            DataQualityFinding(
                code=code,
                severity="warning",
                message=message,
                evidence_ids=sorted(set(references)),
                client_id=client_id,
                portfolio_id=portfolio_id,
            )
        )

    for _, client in tables["clients"].iterrows():
        client_id = str(client["client_id"])
        client_rows = holdings.loc[holdings["client_id"].eq(client_id)]
        if client_rows.empty:
            append(
                "PHASE_A_HOLDINGS_UNAVAILABLE",
                "No eligible holdings observation; absent positions are not zero wealth.",
                [evidence_id("clients", client)],
                client_id,
            )
            continue
        snapshot = str(client_rows["snapshot_date"].max())
        latest = client_rows.loc[client_rows["snapshot_date"].eq(snapshot)]
        holding_ids = [evidence_id("holdings", row) for _, row in latest.iterrows()]
        if snapshot < cutoff:
            append(
                "PHASE_A_STALE_SNAPSHOT",
                f"Latest supplied holdings are dated {snapshot}, before As-of Date {cutoff}; "
                "current availability and market values are unconfirmed.",
                holding_ids,
                client_id,
            )
        total = float(latest["market_value_usd"].sum())
        for _, position in latest.iterrows():
            reference = evidence_id("holdings", position)
            portfolio_id = str(position["portfolio_id"])
            if pd.isna(position["cost_basis_base"]):
                append(
                    "PHASE_A_MISSING_COST_BASIS",
                    "Cost basis is unknown. Unrealised P&L is incomplete; do not impute zero "
                    "or calculate disposal tax from this position.",
                    [reference],
                    client_id,
                    portfolio_id,
                )
            valuation = pd.Timestamp(position["valuation_date"])
            weight = float(position["market_value_usd"]) / total if total > 0 else 0
            if valuation < pd.Timestamp(cutoff) - pd.DateOffset(months=6) and weight > 0.25:
                append(
                    "PHASE_A_MATERIAL_STALE_VALUATION",
                    f"High materiality: valuation dated {valuation.date()} represents "
                    f"{weight * 100:.2f}% of household reported value. An unchanged mark is "
                    "not a current executable price or reliable exit-liquidity estimate.",
                    holding_ids,
                    client_id,
                    portfolio_id,
                )
            if pd.isna(position["sector"]) or not str(position["sector"]).strip():
                append(
                    "PHASE_A_UNKNOWN_SECTOR",
                    "Sector is unknown; retain an explicit unknown bucket instead of "
                    "dropping this holding from exposure denominators.",
                    [reference, f"instruments:{position['instrument_id']}"],
                    client_id,
                    portfolio_id,
                )
        deposits = latest.loc[
            latest["asset_class"].eq("Cash and Equivalents") & latest["liquidity_tier"].ne("Daily")
        ]
        if not deposits.empty:
            append(
                "PHASE_A_NONDAILY_CASH",
                "Cash and short-term deposits include non-Daily holdings. Exclude them "
                "from Daily-cash funding cover and confirm maturity or withdrawal terms.",
                [evidence_id("holdings", row) for _, row in deposits.iterrows()],
                client_id,
            )
        client_transactions = transactions.loc[transactions["client_id"].eq(client_id)]
        if not transactions.empty and client_transactions.empty:
            append(
                "PHASE_A_LEDGER_UNAVAILABLE",
                "No settled transaction records are available for this Client by the As-of Date. "
                "Income and fees are unavailable, not established as zero.",
                [evidence_id("clients", client)],
                client_id,
            )
        for _, transfer in client_transactions.loc[
            client_transactions["transaction_type"].eq("Transfer In")
        ].iterrows():
            transferred = latest.loc[latest["portfolio_id"].eq(transfer["portfolio_id"])]
            if not transferred.empty:
                append(
                    "PHASE_A_TRANSFER_TAX_BASIS_UNVERIFIED",
                    "Transferred book bases are not validated original purchase or inherited "
                    "tax-lot bases. Request tax-lot history from the transferring institution "
                    "or estate executor before disposal-tax advice; retain supported mandate "
                    "and funding calculations.",
                    [evidence_id("transactions", transfer)]
                    + [evidence_id("holdings", row) for _, row in transferred.iterrows()],
                    client_id,
                    str(transfer["portfolio_id"]),
                )
    if transactions.empty:
        append(
            "PHASE_A_LEDGER_UNAVAILABLE",
            "No settled transaction records are available by the As-of Date. Income, fees "
            "and activity reconciliation are unavailable, not established as zero.",
            [evidence_id("clients", row) for _, row in tables["clients"].iterrows()],
        )
    else:
        append(
            "PHASE_A_LEDGER_UNRECONCILED",
            "Transactions and holdings have not been reconciled as a complete cash ledger. "
            "Income and fees are separate receipts/payments, not a validated total return; "
            "do not roll forward or repair synthetic holdings from transactions.",
            [evidence_id("transactions", row) for _, row in transactions.iterrows()],
        )
    for mandate_code, rows in tables["mandates"].groupby("mandate_code", sort=True):
        target_sum = float(rows["target_pct"].sum())
        if not math.isclose(target_sum, 100.0, abs_tol=0.01):
            append(
                "PHASE_A_INCOMPLETE_MANDATE_TARGET",
                f"Mandate {mandate_code} targets total {target_sum:.2f}%, not 100%. "
                "Bands can still be tested; target-based rebalancing is underdefined.",
                [evidence_id("mandates", row) for _, row in rows.iterrows()],
            )
    _purchase_basis_findings(holdings, transactions, append)
    _facility_activity_findings(tables["credit_facilities"], transactions, cutoff, append)
    return sorted(
        findings,
        key=lambda item: (item.code, item.client_id or "", item.portfolio_id or "", item.message),
    )


def _purchase_basis_findings(holdings, transactions, append):
    purchases = transactions.loc[
        transactions["transaction_type"].isin(["Buy", "Structured Product Subscription"])
    ]
    for (portfolio_id, instrument_id), rows in holdings.groupby(
        ["portfolio_id", "instrument_id"], sort=True
    ):
        rows = rows.sort_values("snapshot_date")
        first, last = rows.iloc[0], rows.iloc[-1]
        if first["snapshot_date"] == last["snapshot_date"]:
            continue
        matching = purchases.loc[
            purchases["portfolio_id"].eq(portfolio_id)
            & purchases["instrument_id"].eq(instrument_id)
            & purchases["trade_date"].gt(first["snapshot_date"])
            & purchases["settlement_date"].le(last["snapshot_date"])
        ]
        if matching.empty or not matching["currency"].eq(last["portfolio_ccy"]).all():
            continue
        if pd.isna(first["cost_basis_base"]) or pd.isna(last["cost_basis_base"]):
            continue
        quantity_added = float(last["quantity"] - first["quantity"])
        if not math.isclose(quantity_added, float(matching["quantity"].sum()), abs_tol=1e-8):
            continue
        expected_basis = float(first["cost_basis_base"] - matching["amount"].sum())
        difference = expected_basis - float(last["cost_basis_base"])
        if abs(difference) > 0.02:
            append(
                "PHASE_A_PURCHASE_BASIS_MISMATCH",
                f"Opening basis plus matched same-currency purchases differs from reported "
                f"ending basis by {difference:,.2f} {last['portfolio_ccy']}. Quantities reconcile "
                "but the tax/cost ledger does not; retain reported basis with this exception.",
                [evidence_id("holdings", first), evidence_id("holdings", last)]
                + [evidence_id("transactions", row) for _, row in matching.iterrows()],
                str(last["client_id"]),
                str(portfolio_id),
            )


def _facility_activity_findings(facilities, transactions, cutoff, append):
    dates = sorted(
        column.removeprefix("drawn_")
        for column in facilities.columns
        if column.startswith("drawn_") and column.removeprefix("drawn_") <= cutoff
    )
    if len(dates) < 2:
        return
    first, last = dates[0], dates[-1]
    for _, facility in facilities.iterrows():
        activity = transactions.loc[
            transactions["portfolio_id"].eq(facility["collateral_portfolio_id"])
            & transactions["transaction_type"].eq("Facility Drawdown")
            & transactions["trade_date"].gt(first)
            & transactions["settlement_date"].le(last)
        ]
        if not activity["currency"].eq(facility["facility_ccy"]).all():
            continue
        change = float(facility[f"drawn_{last}"] - facility[f"drawn_{first}"])
        residual = change - float(activity["amount"].sum())
        if abs(residual) > 0.02:
            append(
                "PHASE_A_FACILITY_ACTIVITY_UNRECONCILED",
                f"Observed drawn-balance change less documented facility drawdowns leaves "
                f"{residual:,.2f} {facility['facility_ccy']} unexplained. Repayments or other "
                "activity may be missing; do not overwrite balances or infer use of proceeds.",
                [evidence_id("credit_facilities", facility)]
                + [evidence_id("transactions", row) for _, row in activity.iterrows()],
                str(facility["client_id"]),
                str(facility["collateral_portfolio_id"]),
            )
