"""Exact Fact and Signal comparisons with an optional analytics materiality predicate."""

from __future__ import annotations

from collections.abc import Callable

from app.pipeline.schemas import ChangeReport, FactBundle, FactChange, SignalChange, SignalSet


def compare_client(
    facts: FactBundle,
    signals: SignalSet,
    prior_facts: FactBundle | None,
    prior_signals: SignalSet | None,
    *,
    changed_source_files: list[str],
    hashes_match: bool = False,
    material: Callable[[float, float], bool] = lambda before, after: before != after,
) -> ChangeReport:
    """Compare stable ids, numeric values and severities, excluding timestamps and run ids."""
    fact_changes = []
    signal_changes = []
    same_as_of = prior_facts is not None and prior_facts.as_of == facts.as_of
    if not hashes_match or not same_as_of or prior_facts is None:
        old = {item.id: item for item in prior_facts.facts} if prior_facts else {}
        new = {item.id: item for item in facts.facts}
        for key in sorted(old.keys() | new.keys()):
            before = old[key].value if key in old else None
            after = new[key].value if key in new else None
            if key not in old or key not in new or material(old[key].value, new[key].value):
                fact_changes.append(
                    FactChange(
                        fact_id=key,
                        change="added"
                        if key not in old
                        else "removed"
                        if key not in new
                        else "changed",
                        before=before,
                        after=after,
                    )
                )
        old_signals = {item.id: item for item in prior_signals.signals} if prior_signals else {}
        new_signals = {item.id: item for item in signals.signals}
        for key in sorted(old_signals.keys() | new_signals.keys()):
            before = old_signals[key].severity if key in old_signals else None
            after = new_signals[key].severity if key in new_signals else None
            if before != after:
                signal_changes.append(
                    SignalChange(
                        signal_id=key,
                        change="added"
                        if key not in old_signals
                        else "removed"
                        if key not in new_signals
                        else "changed",
                        before=before,
                        after=after,
                    )
                )
    mode = (
        "first_seen"
        if prior_facts is None
        else "incremental_update"
        if fact_changes or signal_changes
        else "no_material_change"
    )
    return ChangeReport(
        client_id=facts.client_id,
        run_id=facts.run_id,
        as_of=facts.as_of,
        prior_run_id=prior_facts.run_id if prior_facts else None,
        processing_mode=mode,
        fact_changes=fact_changes,
        signal_changes=signal_changes,
        changed_fact_ids=[item.fact_id for item in fact_changes],
        affected_signal_ids=[item.signal_id for item in signal_changes],
        changed_source_files=sorted(changed_source_files),
    )
