from datetime import date
from pathlib import Path

import pytest

from app.monday_brief import MondayBriefProjection, build_monday_brief
from app.monday_brief.models import MandateFact

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def projection() -> MondayBriefProjection:
    return build_monday_brief(DATA, as_of=date(2026, 8, 26))


def test_pipeline_ranks_all_clients_and_puts_margarethe_first(
    projection: MondayBriefProjection,
) -> None:
    assert len(projection.ranking) == 20
    assert projection.ranking[0].client_id == "CL-0003"
    assert projection.ranking[0].components.model_dump() == {
        "gap": 93,
        "deadline": 91,
        "consequence": 100,
    }


def test_margarethe_pre_read_links_belief_to_exact_mandate_fact(
    projection: MondayBriefProjection,
) -> None:
    pre_read = projection.pre_reads["CL-0003"]
    fact = next(fact for fact in projection.facts["CL-0003"] if fact.kind == "mandate_gap")

    assert isinstance(fact, MandateFact)
    assert pre_read.gap.belief == "I have never taken a risk with money."
    assert pre_read.gap.data == "Equity is 71.5% against a 30% limit."
    assert "rm_notes:N-005" in pre_read.gap.citations
    assert fact.numbers.gap_pct == 41.5
    assert fact.source_rows
    assert pre_read.language == "German"
    assert pre_read.opening.text.startswith("Sie wünschen")


def test_narrated_sentences_always_carry_citations(
    projection: MondayBriefProjection,
) -> None:
    for pre_read in projection.pre_reads.values():
        lines = [*pre_read.what_changed, *pre_read.rules_money, pre_read.opening]
        assert all(line.citations for line in lines)


def test_al_mansoori_scenarios_are_precomputed_ranges(
    projection: MondayBriefProjection,
) -> None:
    scenarios = projection.scenarios["CL-0019"]

    assert scenarios.reopens.low_pct == -7.2
    assert scenarios.reopens.high_pct == -1.4
    assert scenarios.escalates.low_pct == -1.0
    assert scenarios.escalates.high_pct == 6.5
    assert scenarios.reopens.bullets[0].text.startswith("Shipping:")
    assert scenarios.reopens.disclaimer == "Precomputed range, not a forecast."


def test_evidence_resolves_to_source_rows(projection: MondayBriefProjection) -> None:
    fact = next(fact for fact in projection.facts["CL-0003"] if fact.kind == "mandate_gap")
    resolved = [projection.evidence[citation] for citation in fact.source_rows]

    assert any(record.source == "data/mandates.csv" for record in resolved)
    assert any(record.source == "data/holdings.csv" for record in resolved)


def test_workflow_context_is_cited(projection: MondayBriefProjection) -> None:
    for pre_read in projection.pre_reads.values():
        assert all(item.citations for item in pre_read.workflow)
        assert all(
            citation in projection.evidence
            for item in pre_read.workflow
            for citation in item.citations
        )
