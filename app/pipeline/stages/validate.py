"""Structural publication gate and evidence-backed quality disclosures."""

from __future__ import annotations

from contextlib import suppress
from datetime import date
from typing import Any, cast

from app.pipeline.errors import SourceDiagnostic, SourceValidationError
from app.pipeline.evidence import evidence_id, native
from app.pipeline.schemas import DataQualityFinding, DataQualityReport, Evidence, EvidenceMap
from app.pipeline.sources import NOTE_FIELDS
from app.pipeline.stages.ingest import IngestedSources

KEYS = {
    "clients": ["client_id"],
    "portfolios": ["portfolio_id"],
    "holdings": ["snapshot_date", "portfolio_id", "instrument_id"],
    "instruments": ["instrument_id"],
    "transactions": ["transaction_id"],
    "commitments": ["commitment_id"],
    "planned_cash_needs": ["need_id"],
    "credit_facilities": ["facility_id"],
    "mandates": ["mandate_code", "asset_class"],
    "market_context": ["snapshot_date", "series_id"],
}


class QualityValidationError(SourceValidationError):
    """Aggregated structural failures with a serializable quality report."""

    def __init__(self, diagnostics: list[SourceDiagnostic], report: DataQualityReport):
        self.report = report
        super().__init__(diagnostics)


def source_evidence(sources: IngestedSources) -> EvidenceMap:
    """Resolve canonical row identifiers without changing source records."""
    entries: dict[str, Evidence] = {}
    for table, frame in sources.tables.items():
        for index, row in cast(Any, frame).iterrows():
            identifier = evidence_id(table, row)
            fields = {str(key): native(value) for key, value in row.items()}
            entries.setdefault(
                identifier,
                Evidence(
                    id=identifier,
                    kind=table,
                    title=identifier,
                    source=f"data/{table}.csv",
                    source_file=f"{table}.csv",
                    row_index=int(str(index)) + 2,
                    fields=fields,
                    record=fields,
                ),
            )
    for index, note in enumerate(sources.notes, 1):
        identifier = f"rm_notes:{note.get('note_id', index)}"
        entries.setdefault(
            identifier,
            Evidence(
                id=identifier,
                kind="rm_notes",
                title=identifier,
                source="data/rm_notes.json",
                source_file="rm_notes.json",
                row_index=index,
                fields=note,
                record=note,
            ),
        )
    return EvidenceMap(as_of=sources.as_of, entries=entries)


def validate_sources(sources: IngestedSources) -> DataQualityReport:
    """Return warning disclosures; raise on structural errors before publication."""
    diagnostics = list(sources.diagnostics)
    findings: list[DataQualityFinding] = []

    def warn(code: str, message: str, ids: list[str], row: Any = None) -> None:
        findings.append(
            DataQualityFinding(
                code=code,
                severity="warning",
                message=message,
                evidence_ids=ids,
                client_id=row.get("client_id") if row is not None else None,
                portfolio_id=row.get("portfolio_id") if row is not None else None,
            )
        )

    def error(
        file: str, code: str, message: str, row: int | None = None, field: str | None = None
    ) -> None:
        diagnostics.append(SourceDiagnostic(file, code, message, row=row, field=field))

    # Missing structure prevents safe traversal, but all files were already attempted.
    if not diagnostics:
        tables = sources.tables
        clients = set(tables["clients"]["client_id"])
        portfolios = set(tables["portfolios"]["portfolio_id"])
        instruments = set(tables["instruments"]["instrument_id"])
        mandates = set(tables["mandates"]["mandate_code"])
        ownership = dict(
            zip(
                tables["portfolios"]["portfolio_id"], tables["portfolios"]["client_id"], strict=True
            )
        )
        for table, frame in tables.items():
            keys = KEYS.get(table, [])
            if keys:
                for index, row in cast(Any, frame).iterrows():
                    if any(not str(row[key]).strip() for key in keys):
                        error(
                            f"{table}.csv",
                            "missing_identifier",
                            "identifier must not be blank",
                            int(str(index)) + 2,
                        )
                for index in frame.index[frame.duplicated(keys, keep=False)]:
                    error(
                        f"{table}.csv",
                        "duplicate_identifier",
                        "source key is duplicated",
                        int(str(index)) + 2,
                    )
            for index, row in cast(Any, frame).iterrows():
                for field, valid in [
                    ("client_id", clients),
                    ("portfolio_id", portfolios),
                    ("collateral_portfolio_id", portfolios),
                    ("instrument_id", instruments),
                ]:
                    if field not in row or (
                        table == "transactions" and field == "instrument_id" and not row[field]
                    ):
                        continue
                    if row[field] not in valid:
                        error(
                            f"{table}.csv",
                            "orphan_reference",
                            f"{row[field]!r} does not resolve",
                            int(str(index)) + 2,
                            field,
                        )
                portfolio = row.get("portfolio_id", row.get("collateral_portfolio_id"))
                if portfolio in ownership and row.get("client_id") != ownership[portfolio]:
                    error(
                        f"{table}.csv",
                        "inconsistent_client",
                        "portfolio belongs to another client",
                        int(str(index)) + 2,
                    )
        for (snapshot, client_id), group in cast(Any, tables["holdings"]).groupby(
            ["snapshot_date", "client_id"], sort=True
        ):
            if group["market_value_base"].sum() <= 0:
                error(
                    "holdings.csv",
                    "invalid_portfolio_total",
                    f"{client_id} must have a positive total at {snapshot}",
                    int(str(group.index[0])) + 2,
                    "market_value_base",
                )
        for _, row in tables["holdings"].iterrows():
            if row["valuation_date"] != row["snapshot_date"]:
                warn(
                    "LAGGED_VALUATION",
                    "Valuation date differs from snapshot date.",
                    [evidence_id("holdings", row)],
                    row,
                )
        for _, row in tables["portfolios"].iterrows():
            if row["mandate_code"] not in mandates:
                warn(
                    "MANDATE_NOT_MEASURED",
                    "Portfolio mandate has no measurement bands.",
                    [evidence_id("portfolios", row)],
                    row,
                )
        for client_id, group in tables["portfolios"].groupby("client_id", sort=True):
            if len(group) > 1:
                warn(
                    "MULTI_PORTFOLIO_CLIENT",
                    "Client has multiple portfolios.",
                    [evidence_id("portfolios", row) for _, row in group.iterrows()],
                    {"client_id": client_id},
                )
        seen_notes: set[str] = set()
        for index, note in enumerate(sources.notes, 1):
            for field in NOTE_FIELDS:
                if not isinstance(note.get(field), str) or not note[field].strip():
                    error(
                        "rm_notes.json",
                        "missing_field",
                        f"{field} must be a nonempty string",
                        index,
                        field,
                    )
            identifier = str(note.get("note_id", ""))
            if identifier in seen_notes:
                error(
                    "rm_notes.json",
                    "duplicate_identifier",
                    "note id is duplicated",
                    index,
                    "note_id",
                )
            seen_notes.add(identifier)
            try:
                if date.fromisoformat(note.get("note_date", "")).isoformat() != note.get(
                    "note_date"
                ):
                    raise ValueError("not ISO date")
            except (ValueError, TypeError):
                error("rm_notes.json", "invalid_date", "expected YYYY-MM-DD", index, "note_date")
            if note.get("client_id") not in clients:
                warn(
                    "NOTE_UNKNOWN_CLIENT",
                    "RM note references an unknown client.",
                    [f"rm_notes:{identifier}"],
                    note,
                )
        events = tables["event_log"]
        for _, row in events[events.duplicated(keep=False)].iterrows():
            warn(
                "DUPLICATE_EVENT", "Duplicate event source record.", [evidence_id("event_log", row)]
            )
        market = tables["market_context"]
        snapshots = sorted(set(tables["holdings"]["snapshot_date"]) | set(market["snapshot_date"]))
        for snapshot in snapshots:
            fx = market[(market["snapshot_date"] == snapshot) & (market["category"] == "FX")]
            quotes = set(fx["series_id"])
            for index, row in fx.iterrows():
                if row["value"] <= 0:
                    error(
                        "market_context.csv",
                        "invalid_fx_quote",
                        "FX quote must be positive",
                        int(str(index)) + 2,
                        "value",
                    )
            for table, currency_fields in [
                ("holdings", ["instrument_ccy", "portfolio_ccy"]),
                ("planned_cash_needs", ["currency"]),
                ("commitments", ["currency"]),
                ("credit_facilities", ["facility_ccy"]),
                ("portfolios", ["base_currency"]),
            ]:
                frame = tables[table]
                if "snapshot_date" in frame:
                    frame = frame[frame["snapshot_date"] == snapshot]
                for _, row in cast(Any, frame).iterrows():
                    for currency in sorted({row[field] for field in currency_fields}):
                        if (
                            currency != "USD"
                            and f"USD{currency}" not in quotes
                            and f"{currency}USD" not in quotes
                        ):
                            warn(
                                "MISSING_FX_PATH",
                                f"No USD FX route for {currency} at {snapshot}.",
                                [evidence_id(table, row)],
                                row,
                            )
    for diagnostic in diagnostics:
        ids: list[str] = []
        table = diagnostic.file.removesuffix(".csv")
        if diagnostic.row is not None:
            if table in sources.tables:
                frame = sources.tables[table]
                index = diagnostic.row - 2
                if index in frame.index:
                    with suppress(KeyError):
                        ids = [evidence_id(table, frame.loc[index])]
            elif diagnostic.file == "rm_notes.json":
                note = sources.notes[diagnostic.row - 1]
                if note.get("note_id"):
                    ids = [f"rm_notes:{note['note_id']}"]
        findings.append(
            DataQualityFinding(
                code=diagnostic.code, severity="error", message=str(diagnostic), evidence_ids=ids
            )
        )
    report = DataQualityReport(as_of=sources.as_of, findings=findings)
    if diagnostics:
        raise QualityValidationError(diagnostics, report)
    return report
