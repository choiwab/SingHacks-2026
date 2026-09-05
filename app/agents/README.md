# Member 2: meeting-pack agents

The hard migration from `app/client_flow` is complete. All three agents and graph controls live
here; communication replay and TF-IDF retrieval live in `app/mcp`. There are no compatibility exports.
The graph runs independently of the dashboard. The incoming data-team migration removed the
Monday Brief API; the frontend still needs the replacement API/view-model integration.

## Run the offline example

```bash
uv run python -m scripts.member_2_demo
uv run python -m scripts.member_2_demo --update
```

The first command prints a complete initial meeting pack paused for joint RM review. The second
approves the initial demo pack, advances both fixtures, and prints the updated pack awaiting fresh
approval, with the previous approved pack retained. All output records identify the verifier as
`golden_fixture_only`. This example neither uses the API key nor connects to Gmail/Teams.

`tests/fixtures/member_2/` contains authored synthetic communications and provisional curated
bundles. See its README for provenance and the financial-score limitation. Calendar records include
`scheduled_at` separately from `occurred_at`; only records available by the as-of cutoff are loaded.

## Integrate with the data team

```python
from app.agents.graph import build_agent_flow

graph = build_agent_flow(
    load_bundle=load_curated_bundle,  # (client_id, as_of: date, revision) -> CuratedClientBundle
    load_communications=load_memory,  # (client_id, as_of: aware datetime, revision) -> ConnectedContext
    verify_pack=verify_meeting_pack,  # (MeetingPack, CuratedClientBundle, ConnectedContext) -> VerificationReport
    record_review=store_review_event,  # optional idempotent upsert by event_id, supplied by M3
    checkpointer=checkpoint_store,  # M3 supplies durable storage; default is in-memory
)
config = {"configurable": {"thread_id": "rm-demo:CL-0003"}}
result = graph.invoke(
    {
        "run_id": "initial-run",
        "client_id": "CL-0003",
        "as_of": "2026-08-26",
        "revision": "initial",
        "trace": [],
    },
    config=config,
)
```

The three callables are required. There is no default passing verifier and no financial builder
inside an agent. `contracts.py` defines the provisional curated input and Member 2's output schemas;
the canonical one-number data-team `Fact` and `Evidence` models are reused. Each model exposes
`model_json_schema()` for contract exchange.

The gate receives copies of the candidate and input artifacts. It must validate financial values,
claim support, events/as-of scope, communication citations, and suitability wording. Communication
citations look like `gmail:record#contenthash:start-end`: `start` and `end` index the exact span in
`CommunicationRecord.text`, while the content hash matches `memory_index.record_versions` in graph
state. The verifier can reconstruct hashes with `record_content()` and `fingerprint()`.

The old raw-source helper, selected-client adapter, citation traversal and pre-read gate have moved
to `app/pipeline/{source_inspection,client_artifacts,evidence,legacy_verification}.py`.
The shared Fact/Evidence contracts live in `app/pipeline/schemas.py`; calculators remain in
`app/analytics`. Raw calculator dictionaries are not agent inputs. Member 3 publishes canonical one-number Facts.
The authored demo fixtures preserve their existing narrative strings in `fact_descriptions`;
the adapter does not add those descriptions to published financial artifacts.
`legacy_verification` does **not** validate
the new meeting pack and is not wired into the graph.

## Review and update

```python
from langgraph.types import Command

approved = graph.invoke(
    Command(
        resume={
            "client_id": "CL-0003",
            "pack_version": result["pack_version"],
            "action": "Approve",
        }
    ),
    config=config,
)
```

An approval covers the whole brief and Memory Card. `Edit` accepts a `changes` mapping from the
opening/talking-point claim IDs to replacement text. Facts and memory claims are read-only. `Flag`
requires `claim_id` and `reason`; `Reject` can include a reason. Invalid or stale requests return
another interrupt with `validation_error`; they do not commit a review or alter the pack. Valid edits
preserve the prior pack, mark RM authorship, run the gate again, and then require approval.
If a temporary input-loading or data-quality failure clears, the next invocation rechecks a
candidate instead of leaving the thread stuck. Verification failures and correction flags still
remain paused when their inputs have not changed.

Reuse the same client-bound thread when supplying a newer `revision`. Loaders must return complete
curated and communication snapshots for that revision. The memory index detects added/edited/deleted
records, updates affected chunks, and reranks the small corpus. Future or other-client records cannot
enter the graph. A changed communication can refresh rationale, the brief and Memory Card without
altering financial values or scores. Unchanged content preserves its actual prior review status.

Member 3 should expose `pack`, `pack_version`, `status`, `issues`, `verification`, `connected_context`,
`last_approved`, and relevant traces through its view-model adapter. For `needs_confirmation`, show
the failed claim/reason and label `last_approved` as an older version with an update warning. Never
present the failed candidate as meeting-ready. No new dashboard or persistence API was added here.

`record_review` receives stable event IDs and may be retried during graph resume. Upsert rather than
append blindly. If the sink fails, the graph does not finalize the approval. New review requests must
include the current pack version. Use a separate thread per client. Trace/history are kept in memory
for the small hackathon session; durable history, retention and concurrent request serialization belong
to Member 3's storage/API layer.

## Optional OpenAI generation

Offline mode is the default even when `.env` exists. `.env` is ignored and is not loaded by the Python
modules. Copy the names from `.env.example` into your local environment; select a model available to
your account that supports Responses structured output. To explicitly opt in:

```bash
uv run --env-file .env python -m scripts.member_2_demo --live
```

Set both `OPENAI_API_KEY` and `OPENAI_MODEL`. The adapter uses the documented
[Responses structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs)
via Python's standard HTTP library, a 15-second socket timeout, no retry loop, and `store: false`.
Missing configuration, provider errors, refusals/incomplete responses and malformed structured output
fall back to deterministic generation; the trace records the mode without logging secrets.

The model can phrase the opening, talking points and questions. It cannot replace IDs, citations,
scores, financial facts or memory excerpts. Its text still goes through the injected Evidence Gate;
a gate failure pauses the graph, without triggering a rewrite. The example's frozen-claim verifier
will normally reject novel model wording: supply Member 4's real verifier for live integration.
Live requests have not been made during implementation; the adapter is covered with mocked responses.

Live MCP transports, actual external-account retrieval, recording real connector responses and neural
embeddings remain optional future work. The current `app/mcp` module is honest fixture replay with
`synthetic_fixture` provenance and `Cached` availability, not a network MCP implementation.

## Verification

```bash
uv run pytest tests/test_agents.py tests/test_memory.py tests/test_connectors.py
uv run ruff check .
pnpm typecheck:python
```

Acceptance tests cover joint approval, invalid/stale review recovery, immutable facts/memory,
correction flags, all update cases, prior-approved fallback, source isolation, precise citation spans,
record edits/deletions, deterministic ordering, and optional-provider fallback. Golden files are
reviewable expected artifacts, not a substitute for the data team's final Evidence Gate.

## Optional M3 offline integration

`app.pipeline.member2_bridge.member2_hooks(store, load_communications=...)` connects the
three deterministic generation nodes to M3's persisted lifecycle. Pass its result as `agents`
to `PipelineRuntime` or `create_app`. The default loader explicitly reports every communication
source as not connected. A supplied loader must choose complete snapshots by the immutable
run ID, not mutable global state. The demo's authored communications only cover CL-0003.

The bridge preserves the full candidate pack and hash, MemoryIndex snapshot, exact communication
records, source statuses, retrieval log and generation traces in the ledger. Review remains
owned by M3, without creating an independent LangGraph review/checkpoint store. This is an
opt-in generation connection, not a complete meeting-ready integration: M4's final Signal
mapping and verifier remain required. Nonempty Signals require an explicitly supplied
`signal_adapter`; this adapter never invents scores, topics or uncertainty wording.

With current legacy analytics, 16 clients produce deterministic candidate packs and four
(CL-0009, CL-0010, CL-0013, CL-0015) fail context validation because legacy deadline Facts
lack evidence. All 20 remain unverified. The existing lifecycle caches by financial run;
independent communication refresh and pack-aware review edits require additional integration
before enabling full interactive reviews.
