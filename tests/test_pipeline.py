from app.pipeline import build_app_data


def test_pipeline_ranks_all_clients_and_puts_margarethe_first() -> None:
    data = build_app_data()

    assert len(data["ranking"]) == 20
    assert data["ranking"][0]["client_id"] == "CL-0003"
    assert data["ranking"][0]["components"] == {
        "gap": 93,
        "deadline": 91,
        "consequence": 100,
    }


def test_margarethe_pre_read_links_belief_to_exact_mandate_fact() -> None:
    data = build_app_data()
    pre_read = data["pre_reads"]["CL-0003"]
    fact = next(fact for fact in data["facts"]["CL-0003"] if fact["id"].endswith("mandate-gap"))

    assert pre_read["gap"]["belief"] == "I have never taken a risk with money."
    assert pre_read["gap"]["data"] == "Equity is 71.5% against a 30% limit."
    assert "rm_notes:N-005" in pre_read["gap"]["citations"]
    assert fact["numbers"]["gap_pct"] == 41.5
    assert fact["source_rows"]
    assert pre_read["language"] == "German"
    assert pre_read["opening"]["text"].startswith("Sie wünschen")


def test_narrated_sentences_always_carry_citations() -> None:
    data = build_app_data()

    for pre_read in data["pre_reads"].values():
        lines = [
            *pre_read["what_changed"],
            *pre_read["rules_money"],
            pre_read["opening"],
        ]
        assert all(line["citations"] for line in lines)


def test_al_mansoori_scenarios_are_precomputed_ranges() -> None:
    data = build_app_data()
    scenarios = data["scenarios"]["CL-0019"]

    assert scenarios["reopens"]["low_pct"] == -7.2
    assert scenarios["reopens"]["high_pct"] == -1.4
    assert scenarios["escalates"]["low_pct"] == -1.0
    assert scenarios["escalates"]["high_pct"] == 6.5
    assert scenarios["reopens"]["bullets"][0]["text"].startswith("Shipping:")
    assert scenarios["reopens"]["disclaimer"] == "Precomputed range, not a forecast."


def test_evidence_resolves_to_source_rows() -> None:
    data = build_app_data()
    mandate = next(fact for fact in data["facts"]["CL-0003"] if fact["id"].endswith("mandate-gap"))

    resolved = [data["evidence"][citation] for citation in mandate["source_rows"]]
    assert any(record["source"] == "data/mandates.csv" for record in resolved)
    assert any(record["source"] == "data/holdings.csv" for record in resolved)
