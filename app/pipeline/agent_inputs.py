"""Publish validated dataset facts and actual RM notes to the agent graph.

The repository dataset is synthetic, as declared in README. These are its original
records, not the separate authored communication fixtures or live integrations.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from numbers import Real
from pathlib import Path

from app.agents.contracts import CuratedClientBundle, fingerprint
from app.analytics.facts import AS_OF, fact_engine
from app.analytics.signals import build_signals
from app.mcp.records import SOURCES, CommunicationRecord, ConnectedContext
from app.pipeline.client_artifacts import _jsonable
from app.pipeline.sources import load_sources


def load_legacy_curated_bundle(
    source_dir: Path, client_id: str, as_of: date, revision: str = "current"
) -> CuratedClientBundle:
    """The revision label is metadata only; content determines the published version."""
    tables, _notes = load_sources(source_dir, as_of=as_of)
    if client_id not in set(tables["clients"]["client_id"]):
        raise ValueError(f"Unknown client: {client_id}")
    scoped = {
        name: frame.loc[frame["client_id"] == client_id].copy()
        if "client_id" in frame.columns
        else frame.copy()
        for name, frame in tables.items()
    }
    for name, field in (
        ("holdings", "snapshot_date"),
        ("market_context", "snapshot_date"),
        ("event_log", "event_date"),
    ):
        scoped[name] = scoped[name].loc[scoped[name][field] <= as_of.isoformat()].copy()
    if scoped["holdings"]["portfolio_ccy"].nunique() != 1:
        raise ValueError("Mixed portfolio reporting currencies require explicit normalization")
    facts_by_client, evidence = fact_engine(scoped, as_of)
    raw_facts = _jsonable(facts_by_client[client_id])
    typed_facts = []
    fact_descriptions = {}
    fact_ids = {}
    portfolio_currency = str(scoped["holdings"].iloc[0]["portfolio_ccy"])
    for fact in raw_facts:
        key = fact["id"].rsplit(":", 1)[-1]
        kind = "change" if key.startswith("change-") else key.replace("-", "_")
        numbers = fact["numbers"]
        if key == "deadline" and scoped["planned_cash_needs"].empty:
            # With no cash need, the engine uses the KYC date; its zero amount
            # is a placeholder, not a sourced financial measurement.
            numbers = {"days": numbers["days"]}
        ids = []
        # The canonical contract has one numeric value per Fact. Keep the engine's
        # formulas and complete inputs, and publish its prose separately for agents.
        for field, value in numbers.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                continue
            monetary = field in {
                "amount",
                "amount_in_portfolio_currency",
                "daily_liquid",
                "delta",
                "value",
            }
            currency = None
            if monetary:
                currency = (
                    numbers.get("portfolio_currency") or portfolio_currency
                    if field in {"amount_in_portfolio_currency", "daily_liquid", "value"}
                    else numbers.get("currency")
                )
            identifier = f"{fact['id']}:{field}"
            typed_facts.append(
                {
                    "id": identifier,
                    "client_id": client_id,
                    "kind": f"{kind}.{field}",
                    "value": float(value),
                    "unit": "percent"
                    if field.endswith("_pct")
                    else "days"
                    if field == "days"
                    else "currency"
                    if monetary
                    else "number",
                    "currency": currency,
                    "formula_id": f"legacy.{key}.{field}",
                    "inputs": numbers,
                    "evidence_ids": sorted(set(fact["source_rows"] + fact["event_ids"])),
                    "as_of": as_of.isoformat(),
                    "confidence": {"high": 1.0, "medium": 0.5, "low": 0.25}[fact["confidence"]],
                }
            )
            if not ids:
                fact_descriptions[identifier] = fact["what"]
            ids.append(identifier)
        fact_ids[fact["id"]] = ids
    evidence_ids = {
        identifier
        for fact in raw_facts
        for identifier in [*fact["source_rows"], *fact["event_ids"]]
    }
    signals = build_signals(client_id, raw_facts)
    for signal in signals:
        signal["fact_ids"] = [
            identifier for original in signal["fact_ids"] for identifier in fact_ids[original]
        ]
    current = scoped["holdings"].loc[scoped["holdings"]["snapshot_date"] == as_of.isoformat()]
    if "valuation_date" in current and (current["valuation_date"] < as_of.isoformat()).any():
        for signal in signals:
            signal["uncertainty"] += (
                " Some positions carry earlier valuation dates; inspect source valuations "
                "before treating the snapshot as fully current."
            )
    payload = {
        "client_id": client_id,
        "as_of": as_of.isoformat(),
        "facts": typed_facts,
        "fact_descriptions": fact_descriptions,
        "signals": signals,
        "evidence": {key: _jsonable(evidence[key]) for key in sorted(evidence_ids)},
    }
    return CuratedClientBundle.model_validate({**payload, "version": fingerprint(payload)})


def load_curated_bundle(
    source_dir: Path, client_id: str, as_of: date, revision: str = "current"
) -> CuratedClientBundle:
    """Load content-addressed Phase A artifacts; revision labels cannot alter source facts."""
    from app.pipeline.agent_projection import project_agent_bundle
    from app.pipeline.loaders import ArtifactStore
    from app.pipeline.runner import run_pipeline

    root = source_dir / "generated/curated"
    manifest = run_pipeline(source_dir=source_dir, as_of=as_of, curated_dir=root, activate=False)
    return project_agent_bundle(ArtifactStore(root), client_id, manifest.run_id)


def note_topics(text: str) -> list[str]:
    # ponytail: explicit keyword tags cover the demo; replace only with labelled evaluations.
    patterns = {
        "who_they_are": r"family|father|husband|wife|daughter|son|retir|inherit|business|griev",
        "personality_and_style": r"understand|language|german|english|prefer|agitat|griev|risk",
        "stated_needs_and_goals": r"want|need|prefer|ask|risk|tax|fund|due|goal|conserv|safe",
        "open_promises": (
            r"follow.up|promis|will send|will arrange|agreed to send|to confirm|"
            r"not yet replied|have not.*modelled|asked for a.*before"
        ),
    }
    return [
        "recent_updates",
        "advice_notes",
        *(name for name, pattern in patterns.items() if re.search(pattern, text, re.I)),
    ]


# Alias kept for callers that imported the pre-rename private name.
_note_topics = note_topics


def load_dataset_notes(
    source_dir: Path, client_id: str, as_of: datetime, revision: str = "current"
) -> ConnectedContext:
    """Preserve verbatim note text and dates; never relabel a note as email or Teams."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Dataset notes require an aware as-of timestamp")
    tables, notes = load_sources(source_dir, as_of=AS_OF)
    if client_id not in set(tables["clients"]["client_id"]):
        raise ValueError(f"Unknown client: {client_id}")
    records = []
    for note in notes:
        if note["client_id"] != client_id:
            continue
        try:
            occurred_at = datetime.combine(
                date.fromisoformat(str(note["note_date"])), time.min, tzinfo=UTC
            )
        except ValueError as exc:
            raise ValueError(f"Invalid date for RM note {note['note_id']}") from exc
        if occurred_at > as_of:
            continue
        records.append(
            CommunicationRecord.model_validate(
                {
                    "id": f"notes:{note['note_id']}",
                    "client_id": client_id,
                    "source": "notes",
                    "version": fingerprint(note),
                    "occurred_at": occurred_at,
                    "retrieved_at": as_of,
                    "participants": [str(note["rm_name"])],
                    "text": note["note"],
                    "topics": note_topics(str(note["note"])),
                    "provenance": "dataset",
                    "availability": "Cached",
                    "based_on": [f"data/rm_notes.json:{note['note_id']}"],
                }
            )
        )
    records.sort(key=lambda item: (item.occurred_at, item.id))
    return ConnectedContext(
        records=records,
        sources={source: "Cached" if source == "notes" else "Not connected" for source in SOURCES},
        retrieval_log=[
            {
                "source": "notes",
                "mode": "dataset_read",
                "client_id": client_id,
                "as_of": as_of.isoformat(),
                "record_ids": [record.id for record in records],
                "date_precision": "day (UTC midnight convention)",
            }
        ],
    )
