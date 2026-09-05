"""Communication revision semantics and one-fetch generation over pinned snapshots."""

from copy import deepcopy
from datetime import UTC, date, datetime, time

import pytest

from app.mcp.connectors import replay_records
from app.pipeline.communications import CommunicationSnapshot
from app.pipeline.graph_adapter import execute_client
from app.pipeline.loaders import ArtifactStore
from app.pipeline.member2_bridge import member2_hooks
from app.pipeline.runner import run_pipeline
from scripts.member_2_demo import FIXTURES

AS_OF = date(2026, 8, 26)
CLIENT = "CL-0003"


def snapshot():
    return CommunicationSnapshot(
        client_id=CLIENT,
        as_of=AS_OF,
        context=replay_records(
            FIXTURES / "communications.initial.json",
            client_id=CLIENT,
            as_of=datetime.combine(AS_OF, time.max, UTC),
        ),
    )


def test_revision_ignores_poll_metadata_and_record_order_without_mutating_snapshot():
    before = snapshot()
    original = before.model_dump(mode="json")
    after = deepcopy(original)
    after["context"]["records"].reverse()
    for record in after["context"]["records"]:
        record["retrieved_at"] = "2026-09-05T12:00:00Z"
    after["context"]["retrieval_log"] = [{"status": "polled again"}]
    assert CommunicationSnapshot.model_validate(after).revision == before.revision
    assert before.model_dump(mode="json") == original


@pytest.mark.parametrize("change", ["edit", "delete", "version", "status", "addition"])
def test_substantive_changes_create_a_revision(change):
    before = snapshot()
    after = before.model_dump(mode="json")
    records = after["context"]["records"]
    if change == "edit":
        records[0]["text"] += " Updated priorities."
    elif change == "delete":
        records.pop()
    elif change == "version":
        records[0]["version"] += "-new"
    elif change == "addition":
        records.append({**records[0], "id": records[0]["id"] + "-new"})
    else:
        source = records[0]["source"]
        after["context"]["sources"][source] = "Live"
        for record in records:
            if record["source"] == source:
                record["availability"] = "Live"
                record["provenance"] = "recorded_live"
    assert CommunicationSnapshot.model_validate(after).revision != before.revision


@pytest.mark.parametrize("invalid", ["client", "future", "duplicate"])
def test_snapshot_rejects_invalid_scope(invalid):
    body = snapshot().model_dump(mode="json")
    records = body["context"]["records"]
    if invalid == "client":
        records[0]["client_id"] = "CL-0004"
    elif invalid == "future":
        records[0]["occurred_at"] = "2026-09-02T00:00:00Z"
    else:
        records.append(deepcopy(records[0]))
    with pytest.raises(ValueError):
        CommunicationSnapshot.model_validate(body)


def test_member2_generation_uses_exact_snapshot_and_fetches_once(tmp_path):
    store = ArtifactStore(tmp_path / "curated")
    manifest = run_pipeline(curated_dir=store.root, as_of=AS_OF)
    calls = []

    def load(client, cutoff, revision):
        calls.append((client, cutoff, revision))
        return snapshot().context

    hooks = member2_hooks(store, load_communications=load)
    assert hooks.communications is not None
    pinned = hooks.communications(CLIENT, AS_OF, manifest.run_id)
    output = execute_client(
        store, CLIENT, manifest.run_id, agents=hooks, communication_snapshot=pinned
    )
    assert calls == [(CLIENT, datetime.combine(AS_OF, time.max, UTC), manifest.run_id)]
    assert output["communication_snapshot"] == pinned.model_dump(mode="json")
    assert output["communication_revision"] == pinned.revision
    assert output["connected_context"] == pinned.context.model_dump(mode="json")["records"]
    assert output["verification_report"]["passed"] is False
    calls.clear()
    automatic = execute_client(store, CLIENT, manifest.run_id, agents=hooks)
    assert len(calls) == 1
    assert automatic["communication_revision"] == pinned.revision
    with pytest.raises(ValueError, match="pinned client and date"):
        execute_client(
            store,
            "CL-0004",
            manifest.run_id,
            agents=hooks,
            communication_snapshot=pinned,
        )
    assert len(calls) == 1


def test_snapshot_accepts_end_of_day_and_rejects_later_absolute_instants():
    body = snapshot().model_dump(mode="json")
    body["context"]["records"][0]["occurred_at"] = "2026-08-27T07:59:59.999999+08:00"
    CommunicationSnapshot.model_validate(body)
    body["context"]["records"][0]["occurred_at"] = "2026-08-27T08:00:00+08:00"
    with pytest.raises(ValueError, match="future record"):
        CommunicationSnapshot.model_validate(body)
