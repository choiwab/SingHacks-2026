from decimal import Decimal

from app.domain import (
    AS_OF_DATE,
    build_case_summary,
    build_connector_previews,
    load_case_rows,
    rehearse,
    run_scenario,
)


def test_case_summary_reconciles_to_source_records() -> None:
    summary = build_case_summary()

    assert summary["as_of"] == AS_OF_DATE
    assert summary["client"]["id"] == "CL-0014"
    assert summary["portfolio"]["aum_m"] == 206.88
    assert summary["portfolio"]["property_value_m"] == 101.43
    assert summary["portfolio"]["property_weight_pct"] == 49.03
    assert summary["portfolio"]["known_cash_m"] == 12.0
    assert summary["portfolio"]["cash_coverage_pct"] == 20.0
    assert summary["facility"]["drawn_m"] == 58.0


def test_case_summary_facility_metrics_are_correct() -> None:
    summary = build_case_summary()

    assert summary["facility"]["lending_value_m"] == 83.57
    assert summary["facility"]["ltv_pct"] == 69.41
    assert summary["facility"]["trigger_pct"] == 70.0
    assert summary["facility"]["decline_to_trigger_pct"] == 0.85
    assert [point["ltv"] for point in summary["facility"]["history"]] == [
        53.93,
        53.53,
        65.62,
        67.96,
        69.41,
    ]


def test_scenario_matches_prd_acceptance_values() -> None:
    scenario = run_scenario()

    assert scenario["is_forecast"] is False
    assert scenario["current"]["portfolio_value_m"] == 206.88
    assert scenario["stressed"]["portfolio_value_m"] == 188.65
    assert scenario["stressed"]["portfolio_change_m"] == -18.23
    assert scenario["stressed"]["lending_value_m"] == 78.44
    assert scenario["stressed"]["lending_change_m"] == -5.13
    assert scenario["stressed"]["ltv_pct"] == 73.94
    assert scenario["stressed"]["cure_m"] == 3.09
    assert scenario["stressed"]["trigger_breached"] is True


def test_scenario_uses_advance_rates_for_lending_value() -> None:
    scenario = run_scenario()
    derived = sum(
        Decimal(str(holding["stressed_value_m"]))
        * Decimal(str(holding["advance_rate_pct"]))
        / Decimal("100")
        for holding in scenario["holdings"]
    )

    assert derived.quantize(Decimal("0.01")) == Decimal("78.44")


def test_only_current_snapshot_enters_case_state() -> None:
    rows = load_case_rows()

    assert len(rows.holdings) == 8
    assert {holding["snapshot_date"] for holding in rows.holdings} == {AS_OF_DATE}
    assert all(event["event_date"] <= AS_OF_DATE for event in rows.events)


def test_rehearsal_preserves_client_goal_and_requires_two_decisions() -> None:
    first = rehearse("project")
    complete = rehearse("project", "resilience")

    assert "property market turns" in first["client_position"]
    assert complete["status"] == "Constructive next step"
    assert "external HKD liquidity" in complete["next_question"]


def test_connector_preview_executes_no_writes_and_no_revenue_estimate() -> None:
    tasks = [
        {
            "id": "TASK-01",
            "title": "Confirm external liquidity",
            "owner": "Priscilla Ong",
            "due": "2026-09-05",
            "system": "CRM task",
        }
    ]

    preview = build_connector_previews(tasks)

    assert preview["writes_executed"] == 0
    assert preview["outcome"]["revenue"] is None
    assert len(preview["connectors"]) == 4
