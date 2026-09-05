"""Shape cleaned Source Records into the frozen agent-facing artifact contracts."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.pipeline.evidence import native
from app.pipeline.schemas import (
    CashNeed,
    ClientProfile,
    Commitment,
    CreditFacility,
    CuratedClientBundle,
    FactBundle,
    Holding,
    LiquidityPosition,
    MandateRule,
    Portfolio,
    RMNote,
    SignalSet,
)
from app.pipeline.stages.clean import CleanedSources


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(key): native(value) for key, value in row.items()} for _, row in frame.iterrows()]


def _portfolio(row: dict[str, Any]) -> Portfolio:
    dates = {
        key[4:]: value for key, value in row.items() if re.fullmatch(r"aum_\d{4}-\d{2}-\d{2}", key)
    }
    rest = {key: value for key, value in row.items() if key not in {f"aum_{day}" for day in dates}}
    return Portfolio.model_validate({**rest, "aum_by_date": dates})


def _facility(row: dict[str, Any]) -> CreditFacility:
    dates = sorted({match[1] for key in row if (match := re.search(r"_(\d{4}-\d{2}-\d{2})$", key))})
    snapshots = [
        {
            "snapshot_date": day,
            **{
                key.removesuffix(f"_{day}"): value
                for key, value in row.items()
                if key.endswith(f"_{day}")
            },
        }
        for day in dates
    ]
    rest = {key: value for key, value in row.items() if not re.search(r"_\d{4}-\d{2}-\d{2}$", key)}
    return CreditFacility.model_validate({**rest, "snapshots": snapshots})


def build_curated_bundle(
    cleaned: CleanedSources, client_id: str, facts: FactBundle, signals: SignalSet
) -> CuratedClientBundle:
    tables = cleaned.clients[client_id]
    portfolios = [_portfolio(row) for row in records(tables["portfolios"])]
    codes = {portfolio.mandate_code for portfolio in portfolios}
    holdings = [Holding.model_validate(row) for row in records(tables["holdings"])]
    latest = max((holding.snapshot_date for holding in holdings), default=None)
    return CuratedClientBundle(
        client_id=client_id,
        run_id=facts.run_id,
        as_of=cleaned.as_of,
        profile=ClientProfile.model_validate(records(tables["clients"])[0]),
        portfolios=portfolios,
        holdings=holdings,
        mandate_rules=[
            MandateRule.model_validate(row)
            for row in records(tables["mandates"])
            if row["mandate_code"] in codes
        ],
        liquidity=[
            LiquidityPosition(
                snapshot_date=holding.snapshot_date,
                portfolio_id=holding.portfolio_id,
                instrument_id=holding.instrument_id,
                liquidity_tier=holding.liquidity_tier,
                market_value_base=holding.market_value_base,
                currency=holding.portfolio_ccy,
                evidence_ids=[
                    f"holdings:{holding.snapshot_date}:{holding.portfolio_id}:{holding.instrument_id}"
                ],
            )
            for holding in holdings
            if holding.snapshot_date == latest
        ],
        credit=[_facility(row) for row in records(tables["credit_facilities"])],
        cash_needs=[CashNeed.model_validate(row) for row in records(tables["planned_cash_needs"])],
        commitments=[Commitment.model_validate(row) for row in records(tables["commitments"])],
        rm_notes=[
            RMNote.model_validate({**note, "evidence_id": f"rm_notes:{note['note_id']}"})
            for note in cleaned.notes
            if note["client_id"] == client_id
        ],
        fact_ids=[fact.id for fact in facts.facts],
        signal_ids=[signal.id for signal in signals.signals],
    )
