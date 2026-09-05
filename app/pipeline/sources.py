"""Source loading, structural validation, and content hashing for the raw dataset."""

from __future__ import annotations

import json
import math
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pandas as pd

from app.pipeline.errors import SourceDiagnostic, SourceValidationError

BASELINE = "2025-12-31"

TABLE_NAMES = (
    "clients",
    "credit_facilities",
    "event_log",
    "holdings",
    "mandates",
    "market_context",
    "planned_cash_needs",
    "portfolios",
)

SOURCE_FILES = (
    "clients.csv",
    "portfolios.csv",
    "holdings.csv",
    "instruments.csv",
    "transactions.csv",
    "mandates.csv",
    "commitments.csv",
    "planned_cash_needs.csv",
    "credit_facilities.csv",
    "market_context.csv",
    "event_log.csv",
    "rm_notes.json",
)

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "clients": {
        "client_id",
        "client_name",
        "country_of_residence",
        "booking_centre",
        "base_currency",
        "risk_profile",
        "risk_tolerance_score",
        "life_stage",
        "kyc_review_due",
        "reporting_language",
    },
    "portfolios": {"portfolio_id", "client_id", "mandate_code", "base_currency"},
    "holdings": {
        "snapshot_date",
        "portfolio_id",
        "client_id",
        "instrument_id",
        "instrument_name",
        "asset_class",
        "sub_asset_class",
        "sector",
        "region",
        "portfolio_ccy",
        "market_value_base",
        "liquidity_tier",
    },
    "mandates": {"mandate_code", "mandate_name", "asset_class", "min_pct", "max_pct"},
    "planned_cash_needs": {
        "need_id",
        "client_id",
        "description",
        "currency",
        "amount",
        "due_from",
        "due_to",
        "certainty",
    },
    "credit_facilities": {
        "facility_id",
        "client_id",
        "facility_ccy",
        "drawn_2026-08-26",
        "lending_value_2026-08-26",
        "ltv_pct_2026-08-26",
        "margin_call_ltv_pct",
    },
    "event_log": {
        "event_date",
        "event_type",
        "region",
        "description",
        "primary_transmission",
        "severity",
    },
    "market_context": {
        "snapshot_date",
        "series_id",
        "series_name",
        "category",
        "unit",
        "value",
    },
}

NOTE_FIELDS = {"note_id", "client_id", "note_date", "rm_name", "channel", "note"}

NUMERIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "clients": ("risk_tolerance_score",),
    "holdings": ("market_value_base",),
    "mandates": ("min_pct", "max_pct"),
    "planned_cash_needs": ("amount",),
    "credit_facilities": (
        "drawn_2026-08-26",
        "lending_value_2026-08-26",
        "ltv_pct_2026-08-26",
        "margin_call_ltv_pct",
    ),
    "market_context": ("value",),
}

DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "clients": ("kyc_review_due",),
    "holdings": ("snapshot_date",),
    "planned_cash_needs": ("due_from", "due_to"),
    "event_log": ("event_date",),
    "market_context": ("snapshot_date",),
}


def source_versions(source_dir: Path) -> tuple[dict[str, str], list[str]]:
    """Return content hashes and readable diagnostics for every expected source."""
    versions: dict[str, str] = {}
    issues: list[str] = []
    for name in SOURCE_FILES:
        path = source_dir / name
        try:
            versions[name] = sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            issues.append(f"{name}: {exc.strerror or 'unreadable'}")
    return versions, issues


def _diagnostic(
    file: str,
    code: str,
    message: str,
    *,
    row: int | None = None,
    field: str | None = None,
) -> SourceDiagnostic:
    return SourceDiagnostic(file=file, code=code, message=message, row=row, field=field)


def _load_sources(
    source_dir: Path,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], list[SourceDiagnostic]]:
    tables: dict[str, pd.DataFrame] = {}
    diagnostics: list[SourceDiagnostic] = []
    for name in TABLE_NAMES:
        path = source_dir / f"{name}.csv"
        try:
            tables[name] = pd.read_csv(path)
        except FileNotFoundError:
            diagnostics.append(_diagnostic(path.name, "missing_file", "required source is missing"))
        except Exception as exc:
            diagnostics.append(_diagnostic(path.name, "invalid_csv", str(exc)))

    notes: list[dict[str, Any]] = []
    notes_path = source_dir / "rm_notes.json"
    try:
        value = json.loads(notes_path.read_text(encoding="utf-8"))
        if isinstance(value, list) and all(isinstance(note, dict) for note in value):
            notes = value
        else:
            diagnostics.append(
                _diagnostic(notes_path.name, "invalid_shape", "expected a list of objects")
            )
    except FileNotFoundError:
        diagnostics.append(
            _diagnostic(notes_path.name, "missing_file", "required source is missing")
        )
    except (OSError, json.JSONDecodeError) as exc:
        diagnostics.append(_diagnostic(notes_path.name, "invalid_json", str(exc)))
    return tables, notes, diagnostics


def _duplicates(
    frame: pd.DataFrame,
    file: str,
    field: str,
    diagnostics: list[SourceDiagnostic],
) -> None:
    if field not in frame:
        return
    for index in frame.index[frame[field].duplicated(keep=False)]:
        diagnostics.append(
            _diagnostic(
                file,
                "duplicate_identifier",
                f"duplicate value {frame.at[index, field]!r}",
                row=int(index) + 2,
                field=field,
            )
        )


def _orphans(
    frame: pd.DataFrame,
    file: str,
    field: str,
    valid: set[str],
    diagnostics: list[SourceDiagnostic],
) -> None:
    if field not in frame:
        return
    for index, value in frame[field].items():
        if str(value) not in valid:
            diagnostics.append(
                _diagnostic(
                    file,
                    "orphan_reference",
                    f"{value!r} does not resolve",
                    row=int(str(index)) + 2,
                    field=field,
                )
            )


def _validate_numeric_columns(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    for name, fields in NUMERIC_COLUMNS.items():
        frame = tables[name]
        for field in fields:
            numeric = cast(pd.Series, pd.to_numeric(frame[field], errors="coerce"))
            invalid = numeric.isna() | ~numeric.map(lambda value: math.isfinite(float(value)))
            for index in frame.index[invalid]:
                diagnostics.append(
                    _diagnostic(
                        f"{name}.csv",
                        "invalid_number",
                        f"expected a finite number, got {frame.at[index, field]!r}",
                        row=int(str(index)) + 2,
                        field=field,
                    )
                )


def _validate_date_columns(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    for name, fields in DATE_COLUMNS.items():
        frame = tables[name]
        for field in fields:
            parsed = pd.to_datetime(frame[field], format="%Y-%m-%d", errors="coerce")
            for index in frame.index[parsed.isna()]:
                diagnostics.append(
                    _diagnostic(
                        f"{name}.csv",
                        "invalid_date",
                        f"expected YYYY-MM-DD, got {frame.at[index, field]!r}",
                        row=int(index) + 2,
                        field=field,
                    )
                )


def _validate_scalar_columns(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    _validate_numeric_columns(tables, diagnostics)
    _validate_date_columns(tables, diagnostics)


def _duplicate_composite(
    frame: pd.DataFrame,
    file: str,
    fields: list[str],
    diagnostics: list[SourceDiagnostic],
) -> None:
    for index in frame.index[frame.duplicated(fields, keep=False)]:
        identity = ":".join(str(frame.at[index, field]) for field in fields)
        diagnostics.append(
            _diagnostic(
                file,
                "duplicate_identifier",
                f"duplicate source identity {identity!r}",
                row=int(index) + 2,
                field=",".join(fields),
            )
        )


def _has_fx_path(market: pd.DataFrame, currency: str, snapshot: str) -> bool:
    if currency == "USD":
        return True
    codes = set(
        market.loc[
            (market["snapshot_date"] == snapshot) & (market["category"] == "FX"), "series_id"
        ].astype(str)
    )
    return f"USD{currency}" in codes or f"{currency}USD" in codes


def _validate_required_columns(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    for name, required in REQUIRED_COLUMNS.items():
        frame = tables.get(name)
        if frame is None:
            continue
        for field in sorted(required - set(frame.columns)):
            diagnostics.append(
                _diagnostic(
                    f"{name}.csv",
                    "missing_column",
                    "required column is missing",
                    field=field,
                )
            )


def _validate_unique_keys(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    holdings = tables["holdings"]
    mandates = tables["mandates"]
    market = tables["market_context"]
    for name, field in (
        ("clients", "client_id"),
        ("portfolios", "portfolio_id"),
        ("planned_cash_needs", "need_id"),
        ("credit_facilities", "facility_id"),
    ):
        _duplicates(tables[name], f"{name}.csv", field, diagnostics)
    _duplicate_composite(
        holdings,
        "holdings.csv",
        ["snapshot_date", "portfolio_id", "instrument_id"],
        diagnostics,
    )
    _duplicate_composite(
        market,
        "market_context.csv",
        ["snapshot_date", "series_id"],
        diagnostics,
    )
    _duplicate_composite(
        mandates,
        "mandates.csv",
        ["mandate_code", "asset_class"],
        diagnostics,
    )
    _duplicate_composite(
        tables["event_log"],
        "event_log.csv",
        [
            "event_date",
            "event_type",
            "region",
            "description",
            "primary_transmission",
            "severity",
        ],
        diagnostics,
    )


def _validate_foreign_keys(
    tables: dict[str, pd.DataFrame], diagnostics: list[SourceDiagnostic]
) -> None:
    clients = tables["clients"]
    portfolios = tables["portfolios"]
    holdings = tables["holdings"]
    mandates = tables["mandates"]
    needs = tables["planned_cash_needs"]
    facilities = tables["credit_facilities"]
    client_ids = set(clients["client_id"].astype(str))
    portfolio_ids = set(portfolios["portfolio_id"].astype(str))
    mandate_codes = set(mandates["mandate_code"].astype(str))
    for frame, file in (
        (portfolios, "portfolios.csv"),
        (holdings, "holdings.csv"),
        (needs, "planned_cash_needs.csv"),
        (facilities, "credit_facilities.csv"),
    ):
        _orphans(frame, file, "client_id", client_ids, diagnostics)
    _orphans(holdings, "holdings.csv", "portfolio_id", portfolio_ids, diagnostics)
    _orphans(portfolios, "portfolios.csv", "mandate_code", mandate_codes, diagnostics)


def _validate_notes(
    notes: list[dict[str, Any]],
    clients: pd.DataFrame,
    diagnostics: list[SourceDiagnostic],
) -> None:
    client_ids = set(clients["client_id"].astype(str))
    note_ids: set[str] = set()
    for index, note in enumerate(notes, start=1):
        for field in sorted(NOTE_FIELDS - set(note)):
            diagnostics.append(
                _diagnostic(
                    "rm_notes.json",
                    "missing_field",
                    "required field is missing",
                    row=index,
                    field=field,
                )
            )
        note_id = str(note.get("note_id", ""))
        if note_id in note_ids:
            diagnostics.append(
                _diagnostic(
                    "rm_notes.json",
                    "duplicate_identifier",
                    f"duplicate value {note_id!r}",
                    row=index,
                    field="note_id",
                )
            )
        note_ids.add(note_id)
        if str(note.get("client_id")) not in client_ids:
            diagnostics.append(
                _diagnostic(
                    "rm_notes.json",
                    "orphan_reference",
                    f"{note.get('client_id')!r} does not resolve",
                    row=index,
                    field="client_id",
                )
            )

    clients_with_notes = {str(note.get("client_id")) for note in notes}
    for client_id in sorted(client_ids - clients_with_notes):
        diagnostics.append(
            _diagnostic("rm_notes.json", "missing_client_note", f"no note for {client_id}")
        )


def _validate_portfolio_snapshots(
    holdings: pd.DataFrame,
    clients: pd.DataFrame,
    snapshot: str,
    diagnostics: list[SourceDiagnostic],
) -> None:
    client_ids = set(clients["client_id"].astype(str))
    holding_client_ids = holdings["client_id"].astype(str)
    holding_snapshots = holdings["snapshot_date"].astype(str)
    for client_id in sorted(client_ids):
        client_rows = holding_client_ids.eq(client_id)
        rows = holdings[client_rows & holding_snapshots.eq(snapshot)]
        if rows.empty:
            diagnostics.append(
                _diagnostic(
                    "holdings.csv",
                    "missing_snapshot",
                    f"no {snapshot} positions for {client_id}",
                )
            )
            continue
        baseline_rows = client_rows & holding_snapshots.eq(BASELINE)
        if not baseline_rows.any():
            diagnostics.append(
                _diagnostic(
                    "holdings.csv",
                    "missing_snapshot",
                    f"no {BASELINE} positions for {client_id}",
                )
            )
        values = cast(pd.Series, pd.to_numeric(rows["market_value_base"], errors="coerce"))
        invalid_values = values.empty or not all(math.isfinite(float(value)) for value in values)
        if invalid_values or values.sum() <= 0:
            diagnostics.append(
                _diagnostic(
                    "holdings.csv",
                    "invalid_portfolio_total",
                    f"{client_id} must have a finite positive current total",
                    field="market_value_base",
                )
            )


def _validate_fx_quotes(
    tables: dict[str, pd.DataFrame],
    snapshot: str,
    diagnostics: list[SourceDiagnostic],
) -> None:
    holdings = tables["holdings"]
    needs = tables["planned_cash_needs"]
    market = tables["market_context"]
    used_currencies = set(needs["currency"].astype(str)) | set(
        holdings["portfolio_ccy"].astype(str)
    )
    for currency in sorted(used_currencies):
        if not _has_fx_path(market, currency, snapshot):
            diagnostics.append(
                _diagnostic(
                    "market_context.csv",
                    "missing_fx_quote",
                    f"no {snapshot} USD route for {currency}",
                    field="series_id",
                )
            )
    current_fx = market[(market["snapshot_date"] == snapshot) & (market["category"] == "FX")]
    fx_values = cast(pd.Series, pd.to_numeric(current_fx["value"], errors="coerce"))
    for index, value in fx_values.items():
        if float(value) <= 0:
            diagnostics.append(
                _diagnostic(
                    "market_context.csv",
                    "invalid_fx_quote",
                    "FX quote must be greater than zero",
                    row=int(str(index)) + 2,
                    field="value",
                )
            )


def _validate_sources(
    tables: dict[str, pd.DataFrame],
    notes: list[dict[str, Any]],
    as_of: date,
    diagnostics: list[SourceDiagnostic],
) -> None:
    _validate_required_columns(tables, diagnostics)
    if diagnostics:
        return

    snapshot = as_of.isoformat()
    _validate_scalar_columns(tables, diagnostics)
    _validate_unique_keys(tables, diagnostics)
    _validate_foreign_keys(tables, diagnostics)
    _validate_notes(notes, tables["clients"], diagnostics)
    _validate_portfolio_snapshots(tables["holdings"], tables["clients"], snapshot, diagnostics)
    _validate_fx_quotes(tables, snapshot, diagnostics)


def load_sources(
    source_dir: Path, *, as_of: date
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Load every raw source and validate it, or raise one aggregated error."""
    source_dir = Path(source_dir)
    tables, notes, diagnostics = _load_sources(source_dir)
    _validate_sources(tables, notes, as_of, diagnostics)
    if diagnostics:
        raise SourceValidationError(diagnostics)
    return tables, notes
