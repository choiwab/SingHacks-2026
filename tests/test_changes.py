from datetime import date

from app.pipeline.changes import compare_client
from app.pipeline.schemas import Fact, FactBundle, Signal, SignalSet

AS_OF = date(2026, 8, 26)
CLIENT = "CL-0003"


def facts(run_id, values, *, as_of=AS_OF):
    return FactBundle(
        run_id=run_id,
        as_of=as_of,
        client_id=CLIENT,
        facts=[
            Fact(
                id=key,
                client_id=CLIENT,
                kind="test",
                value=value,
                unit="USD",
                formula_id="test",
                as_of=as_of,
                confidence=1,
            )
            for key, value in values.items()
        ],
    )


def signals(run_id, severities):
    return SignalSet(
        run_id=run_id,
        as_of=AS_OF,
        client_id=CLIENT,
        signals=[
            Signal(
                id=key, client_id=CLIENT, kind="test", severity=value, priority_score=1, as_of=AS_OF
            )
            for key, value in severities.items()
        ],
    )


def test_first_seen_reports_all_facts_and_signals_added():
    result = compare_client(
        facts("r1", {"f1": 10}),
        signals("r1", {"s1": "high"}),
        None,
        None,
        changed_source_files=["holdings.csv"],
    )
    assert result.processing_mode == "first_seen"
    assert result.prior_run_id is None
    assert result.fact_changes[0].model_dump() == {
        "fact_id": "f1",
        "change": "added",
        "before": None,
        "after": 10,
    }
    assert result.affected_signal_ids == ["s1"]


def test_exact_diff_reports_add_remove_numeric_change_and_severity_change():
    result = compare_client(
        facts("r2", {"new": 20, "value": 12, "same": 10}),
        signals("r2", {"new": "medium", "severity": "critical", "same": "low"}),
        facts("r1", {"gone": 20, "value": 11, "same": 10}),
        signals("r1", {"gone": "medium", "severity": "high", "same": "low"}),
        changed_source_files=["rm_notes.json", "holdings.csv"],
    )
    assert result.processing_mode == "incremental_update"
    assert result.prior_run_id == "r1"
    assert [(f.fact_id, f.change, f.before, f.after) for f in result.fact_changes] == [
        ("gone", "removed", 20, None),
        ("new", "added", None, 20),
        ("value", "changed", 11, 12),
    ]
    assert [(s.signal_id, s.change, s.before, s.after) for s in result.signal_changes] == [
        ("gone", "removed", "medium", None),
        ("new", "added", None, "medium"),
        ("severity", "changed", "high", "critical"),
    ]
    assert result.changed_fact_ids == ["gone", "new", "value"]
    assert result.affected_signal_ids == ["gone", "new", "severity"]
    assert result.changed_source_files == ["holdings.csv", "rm_notes.json"]


def test_unchanged_client_gets_no_material_change_when_other_sources_change():
    result = compare_client(
        facts("r2", {"f1": 10}),
        signals("r2", {"s1": "high"}),
        facts("r1", {"f1": 10}),
        signals("r1", {"s1": "high"}),
        changed_source_files=["rm_notes.json"],
    )
    assert result.processing_mode == "no_material_change"
    assert not result.fact_changes and not result.signal_changes


def test_matching_hashes_short_circuit_the_materiality_predicate():
    def must_not_run(before, after):
        raise AssertionError("Identical input hashes should skip numeric comparisons")

    result = compare_client(
        facts("r1", {"f1": 10}),
        signals("r1", {}),
        facts("r1", {"f1": 10}),
        signals("r1", {}),
        changed_source_files=[],
        hashes_match=True,
        material=must_not_run,
    )
    assert result.processing_mode == "no_material_change"
    assert not result.changed_fact_ids


def test_analytics_can_supply_material_change_predicate():
    result = compare_client(
        facts("r2", {"f1": 10.01}),
        signals("r2", {}),
        facts("r1", {"f1": 10}),
        signals("r1", {}),
        changed_source_files=["holdings.csv"],
        material=lambda before, after: abs(after - before) > 0.1,
    )
    assert result.processing_mode == "no_material_change"


def test_same_source_hashes_do_not_hide_a_changed_as_of_date():
    current = facts("r2", {"f1": 20})
    old = facts("r1", {"f1": 10}, as_of=date(2026, 6, 30))
    result = compare_client(
        current,
        signals("r2", {}),
        old,
        signals("r1", {}),
        changed_source_files=[],
        hashes_match=True,
    )
    assert result.processing_mode == "incremental_update"
    assert result.changed_fact_ids == ["f1"]
