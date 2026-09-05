"""Legacy adaptation publishes only sourced numbers, including KYC deadlines."""

from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import run_pipeline


def test_all_published_facts_have_resolvable_evidence_and_kyc_deadlines_are_sourced(tmp_path):
    manifest = run_pipeline(curated_dir=tmp_path)
    assert len(manifest.client_ids) == 20
    store = ArtifactStore(tmp_path)
    evidence = store.load_evidence_map().entries
    expected = {
        "CL-0009": ("2027-05-29", 276),
        "CL-0010": ("2027-07-19", 327),
        "CL-0013": ("2026-12-06", 102),
        "CL-0015": ("2027-04-11", 228),
    }
    no_needs = set()
    for client in manifest.client_ids:
        facts = {fact.id: fact for fact in store.load_fact_bundle(client).facts}
        assert facts
        for fact in facts.values():
            assert fact.evidence_ids, fact.id
            assert set(fact.evidence_ids) <= evidence.keys(), fact.id
        if not store.load_curated_bundle(client).cash_needs:
            no_needs.add(client)
            due, days = expected[client]
            fact = facts[f"{client}:fact:deadline:days"]
            assert fact.value == days
            assert fact.evidence_ids == [f"clients:{client}"]
            assert fact.inputs["kyc_review_due"] == due
            assert evidence[f"clients:{client}"].record["kyc_review_due"] == due
            assert f"{client}:fact:deadline:amount" not in facts
            assert "amount" not in fact.inputs
    assert no_needs == expected.keys()


def test_actual_zero_cash_need_amount_is_retained_with_source_evidence(tmp_path):
    import csv

    from app.pipeline.runner import DEFAULT_SOURCE_DIR

    overlay = tmp_path / "overlay"
    overlay.mkdir()
    with (DEFAULT_SOURCE_DIR / "planned_cash_needs.csv").open() as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        assert fields is not None
        row = next(row for row in reader if row["need_id"] == "CN-004")
    row["amount"] = "0"
    with (overlay / "planned_cash_needs.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    root = tmp_path / "curated"
    run_pipeline(curated_dir=root, overlay=overlay)
    store = ArtifactStore(root)
    facts = {fact.id: fact for fact in store.load_fact_bundle("CL-0003").facts}
    amount = facts["CL-0003:fact:deadline:amount"]
    assert amount.value == 0
    assert "planned_cash_needs:CN-004" in amount.evidence_ids
    record = store.load_evidence_map().entries["planned_cash_needs:CN-004"]
    assert record.record["amount"] == 0
    assert record.source_file == "fixtures/update/planned_cash_needs.csv"
