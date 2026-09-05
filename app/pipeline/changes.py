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
    changed_context_sections: list[str] | None = None,
    hashes_match: bool = False,
    material: Callable[[float, float], bool] = lambda before, after: before != after,
) -> ChangeReport:
    """Compare Facts, Signal meaning and client context, excluding artifact envelopes.

    Context changes route generation independently, without inventing numeric Fact changes.
    Signal diffs include dependencies so an unchanged severity does not hide changed support.
    """
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
        changed_fact_ids = {item.fact_id for item in fact_changes}
        for key in sorted(old_signals.keys() | new_signals.keys()):
            before = old_signals[key].severity if key in old_signals else None
            after = new_signals[key].severity if key in new_signals else None
            previous = old_signals.get(key)
            current = new_signals.get(key)
            changed_fields = []
            if before != after:
                changed_fields.append("severity")
            if changed_fact_ids.intersection(
                (previous.fact_ids if previous else []) + (current.fact_ids if current else [])
            ):
                changed_fields.append("supporting_facts")
            if previous and current:
                if material(previous.priority_score, current.priority_score):
                    changed_fields.append("priority_score")
                if previous.threshold != current.threshold:
                    changed_fields.append("threshold")
                if previous.score_components != current.score_components:
                    changed_fields.append("score_components")
                if set(previous.fact_ids) != set(current.fact_ids):
                    changed_fields.append("fact_ids")
                if previous.kind != current.kind:
                    changed_fields.append("kind")
                if set(previous.evidence_ids) != set(current.evidence_ids):
                    changed_fields.append("evidence_ids")
            if changed_fields:
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
                        changed_fields=changed_fields,
                        before_priority_score=previous.priority_score if previous else None,
                        after_priority_score=current.priority_score if current else None,
                        before_threshold=previous.threshold if previous else None,
                        after_threshold=current.threshold if current else None,
                    )
                )
    mode = (
        "first_seen"
        if prior_facts is None
        else "incremental_update"
        if fact_changes or signal_changes or changed_context_sections
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
        changed_context_sections=sorted(changed_context_sections or []),
    )
