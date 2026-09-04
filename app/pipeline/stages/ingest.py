"""Read typed source tables without dropping or filtering source records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

import pandas as pd

from app.pipeline.errors import SourceDiagnostic

COLUMNS = {
    "clients": [
        "client_id",
        "client_name",
        "age",
        "gender",
        "nationality",
        "country_of_residence",
        "tax_domicile",
        "booking_centre",
        "rm_id",
        "rm_name",
        "rm_desk",
        "base_currency",
        "wealth_band",
        "total_aum_usd",
        "life_stage",
        "source_of_wealth",
        "risk_profile",
        "risk_tolerance_score",
        "investment_horizon_years",
        "liquidity_needs",
        "objectives",
        "client_since",
        "kyc_review_due",
        "pep_status",
        "reporting_language",
    ],
    "commitments": [
        "commitment_id",
        "client_id",
        "portfolio_id",
        "fund_name",
        "currency",
        "committed",
        "called_to_date",
        "uncalled",
        "expected_call_window",
    ],
    "credit_facilities": [
        "facility_id",
        "client_id",
        "collateral_portfolio_id",
        "facility_type",
        "facility_ccy",
        "credit_limit",
        "interest_rate_pct",
        "margin_call_ltv_pct",
        "drawn_2025-12-31",
        "collateral_market_value_2025-12-31",
        "lending_value_2025-12-31",
        "ltv_pct_2025-12-31",
        "headroom_2025-12-31",
        "drawn_2026-02-27",
        "collateral_market_value_2026-02-27",
        "lending_value_2026-02-27",
        "ltv_pct_2026-02-27",
        "headroom_2026-02-27",
        "drawn_2026-03-31",
        "collateral_market_value_2026-03-31",
        "lending_value_2026-03-31",
        "ltv_pct_2026-03-31",
        "headroom_2026-03-31",
        "drawn_2026-06-30",
        "collateral_market_value_2026-06-30",
        "lending_value_2026-06-30",
        "ltv_pct_2026-06-30",
        "headroom_2026-06-30",
        "drawn_2026-08-26",
        "collateral_market_value_2026-08-26",
        "lending_value_2026-08-26",
        "ltv_pct_2026-08-26",
        "headroom_2026-08-26",
        "utilisation_pct_current",
    ],
    "event_log": [
        "event_date",
        "event_type",
        "region",
        "description",
        "primary_transmission",
        "severity",
    ],
    "holdings": [
        "snapshot_date",
        "portfolio_id",
        "client_id",
        "instrument_id",
        "instrument_name",
        "asset_class",
        "sub_asset_class",
        "sector",
        "region",
        "instrument_ccy",
        "quantity",
        "price_local",
        "market_value_local",
        "portfolio_ccy",
        "market_value_base",
        "market_value_usd",
        "weight_pct",
        "avg_cost_local",
        "cost_basis_base",
        "unrealised_pnl_base",
        "unrealised_pnl_pct",
        "lending_value_base",
        "advance_rate_pct",
        "liquidity_tier",
        "valuation_date",
        "acquired_date",
    ],
    "instruments": [
        "instrument_id",
        "instrument_name",
        "asset_class",
        "sub_asset_class",
        "sector",
        "region",
        "currency",
        "liquidity_tier",
        "underlying_reference",
        "sustainability_excluded",
        "concentration_limit_applies",
        "price_2025-12-31",
        "price_2026-02-27",
        "price_2026-03-31",
        "price_2026-06-30",
        "price_2026-08-26",
    ],
    "mandates": [
        "mandate_code",
        "mandate_name",
        "asset_class",
        "min_pct",
        "target_pct",
        "max_pct",
        "max_single_position_pct",
        "mandate_notes",
    ],
    "market_context": [
        "snapshot_date",
        "series_id",
        "series_name",
        "category",
        "unit",
        "value",
        "snapshot_label",
    ],
    "planned_cash_needs": [
        "need_id",
        "client_id",
        "description",
        "currency",
        "amount",
        "due_from",
        "due_to",
        "recurrence",
        "certainty",
    ],
    "portfolios": [
        "portfolio_id",
        "client_id",
        "portfolio_name",
        "mandate_code",
        "mandate_name",
        "service_model",
        "base_currency",
        "inception_date",
        "benchmark",
        "aum_2025-12-31",
        "aum_2026-02-27",
        "aum_2026-03-31",
        "aum_2026-06-30",
        "aum_2026-08-26",
        "aum_usd_current",
    ],
    "transactions": [
        "transaction_id",
        "trade_date",
        "settlement_date",
        "portfolio_id",
        "client_id",
        "transaction_type",
        "instrument_id",
        "instrument_name",
        "quantity",
        "price_local",
        "currency",
        "amount",
        "narrative",
    ],
}

NUMERIC_FIELDS = set(
    [
        "age",
        "total_aum_usd",
        "risk_tolerance_score",
        "investment_horizon_years",
        "quantity",
        "price_local",
        "market_value_local",
        "market_value_base",
        "market_value_usd",
        "weight_pct",
        "avg_cost_local",
        "cost_basis_base",
        "unrealised_pnl_base",
        "unrealised_pnl_pct",
        "lending_value_base",
        "advance_rate_pct",
        "min_pct",
        "target_pct",
        "max_pct",
        "max_single_position_pct",
        "amount",
        "committed",
        "called_to_date",
        "uncalled",
        "credit_limit",
        "interest_rate_pct",
        "margin_call_ltv_pct",
        "utilisation_pct_current",
        "value",
        "aum_usd_current",
    ]
)
NUMERIC_PREFIXES = (
    "price_",
    "aum_",
    "drawn_",
    "collateral_market_value_",
    "lending_value_",
    "ltv_pct_",
    "headroom_",
)
OPTIONAL_FIELDS = {
    "age",
    "avg_cost_local",
    "cost_basis_base",
    "unrealised_pnl_base",
    "unrealised_pnl_pct",
    "underlying_reference",
}
DATE_FIELDS = {
    "snapshot_date",
    "valuation_date",
    "acquired_date",
    "inception_date",
    "trade_date",
    "settlement_date",
    "due_from",
    "due_to",
    "event_date",
    "client_since",
    "kyc_review_due",
}


@dataclass
class IngestedSources:
    tables: dict[str, pd.DataFrame]
    notes: list[dict[str, Any]]
    as_of: date
    diagnostics: list[SourceDiagnostic] = field(default_factory=list)


def coerce_source_table(
    table: str, source: pd.DataFrame
) -> tuple[pd.DataFrame, list[SourceDiagnostic]]:
    """Type and validate source or overlay cells with the same structural contract."""
    frame = source.copy(deep=True)
    filename = f"{table}.csv"
    columns = COLUMNS[table]
    diagnostics: list[SourceDiagnostic] = []
    for column in columns:
        if column not in frame:
            diagnostics.append(
                SourceDiagnostic(
                    filename, "missing_column", "required column is missing", field=column
                )
            )
            continue
        if column in NUMERIC_FIELDS or column.startswith(NUMERIC_PREFIXES):
            parsed = cast(
                pd.Series, pd.to_numeric(frame[column].replace("", None), errors="coerce")
            )
            for index, value in cast(Any, frame[column]).items():
                optional = column in OPTIONAL_FIELDS or (
                    table == "transactions" and column in {"quantity", "price_local"}
                )
                if (value != "" or not optional) and (
                    bool(pd.isna(cast(Any, parsed[index])))
                    or not float("-inf") < float(cast(Any, parsed[index])) < float("inf")
                ):
                    diagnostics.append(
                        SourceDiagnostic(
                            filename,
                            "invalid_number",
                            f"expected finite number, got {value!r}",
                            row=int(str(index)) + 2,
                            field=column,
                        )
                    )
            if table == "clients" and column in {"age", "risk_tolerance_score"}:
                for index, value in cast(Any, parsed).items():
                    if not pd.isna(value) and float(value).is_integer() is False:
                        diagnostics.append(
                            SourceDiagnostic(
                                filename,
                                "invalid_integer",
                                "expected a whole number",
                                row=int(str(index)) + 2,
                                field=column,
                            )
                        )
            frame[column] = parsed.astype("Float64")
        elif column in DATE_FIELDS:
            for index, value in cast(Any, frame[column]).items():
                try:
                    if date.fromisoformat(value).isoformat() != value:
                        raise ValueError(value)
                except (ValueError, TypeError):
                    diagnostics.append(
                        SourceDiagnostic(
                            filename,
                            "invalid_date",
                            f"expected YYYY-MM-DD, got {value!r}",
                            row=int(str(index)) + 2,
                            field=column,
                        )
                    )
    return frame, diagnostics


def ingest_sources(source_dir: Path, *, as_of: date) -> IngestedSources:
    """Preserve all rows and original indices; validation is a separate stage.

    Dates stay ISO strings so source identities and downstream analytics remain stable.
    All numeric columns use nullable floats. Malformed cells are recorded before coercion.
    """
    result = IngestedSources({}, [], as_of)
    for table in COLUMNS:
        filename = f"{table}.csv"
        try:
            frame = pd.read_csv(Path(source_dir) / filename, dtype=str, keep_default_na=False)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            result.diagnostics.append(
                SourceDiagnostic(
                    filename,
                    "missing_file" if isinstance(exc, FileNotFoundError) else "invalid_csv",
                    str(exc),
                )
            )
            continue
        result.tables[table] = frame
        frame, diagnostics = coerce_source_table(table, frame)
        result.tables[table] = frame
        result.diagnostics.extend(diagnostics)
    try:
        notes = json.loads((Path(source_dir) / "rm_notes.json").read_text())
        if not isinstance(notes, list) or not all(isinstance(note, dict) for note in notes):
            raise ValueError("expected list of note objects")
        result.notes = notes
    except (OSError, ValueError) as exc:
        result.diagnostics.append(
            SourceDiagnostic(
                "rm_notes.json",
                "missing_file" if isinstance(exc, FileNotFoundError) else "invalid_json",
                str(exc),
            )
        )
    return result
