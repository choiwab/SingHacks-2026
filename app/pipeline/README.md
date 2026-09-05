# Pipeline integration

Member 3 publishes typed JSON artifacts. Member 2 consumes the plain Python loader functions
below and owns any LangChain tool wrappers. Financial formulas and verification remain Member 4's
responsibility. Loading an artifact never runs analytics, writes a brief, or calls an agent.

## Agent loaders

```python
from app.pipeline.loaders import (
    ArtifactNotFound,
    load_manifest,
    load_curated_bundle,
    load_fact_bundle,
    load_signal_set,
    load_change_report,
    load_evidence,
    load_data_quality_report,
)

# Pin this run for the whole graph invocation so an update cannot mix versions.
run_id = load_manifest().run_id
bundle = load_curated_bundle("CL-0003", run_id=run_id)
facts = load_fact_bundle("CL-0003", run_id=run_id)
signals = load_signal_set("CL-0003", run_id=run_id)
changes = load_change_report("CL-0003", run_id=run_id)
quality = load_data_quality_report(run_id=run_id, client_id="CL-0003")
evidence = load_evidence(
    [identifier for fact in facts.facts for identifier in fact.evidence_ids],
    run_id=run_id,
)
```

All functions return Pydantic models. `load_evidence` returns `dict[str, Evidence]` and resolves
the complete requested set or raises `ArtifactNotFound`; duplicate IDs produce one entry.
`load_manifest(run_id=None)` accepts a positional run ID. The remaining loaders accept the
optional run ID as a keyword. Client loaders take `client_id` positionally; the quality loader
accepts both `run_id` and `client_id` as optional keywords. Evidence IDs are an iterable of strings.

Omitting `run_id` resolves `latest.json` at the start of each call. A missing latest pointer,
run, client, artifact, or requested evidence ID raises `ArtifactNotFound`, a `FileNotFoundError`
subclass. Invalid identifiers or a path escaping the curated directory raise `ValueError`.
Malformed artifact JSON or schemas fail validation rather than being treated as missing data.
Run IDs contain 12 lowercase hexadecimal characters; client IDs use `CL-0003` format.

The quality report without a client filter covers the whole run. A client-filtered report retains
that client's findings and global findings with no `client_id`, while excluding other clients.
Returned reports retain their run ID and as-of date.

The module functions read `PIPELINE_CURATED_DIR` at call time, defaulting to
`data/generated/curated` relative to the repository. Use `ArtifactStore(root)` for an explicitly
configured store, such as an API instance or test. Its seven `load_*` methods have the same
signatures and behavior as the module functions.

## Published layout

```text
data/generated/curated/
  latest.json
  runs/<run_id>/
    manifest.json
    curated_client_bundle/<client_id>.json
    fact_bundle/<client_id>.json
    signal_set/<client_id>.json
    change_report/<client_id>.json
    evidence_map.json
    data_quality_report.json
```

`latest.json` records `run_id`, `seed_run_id`, and `updated_at`. Published runs are immutable.
The identity is content-addressed from pipeline version, as-of date, source hashes, and overlay
hashes. Git revision is recorded as manifest provenance, not part of run identity. Wall-clock
timestamps appear only in the manifest and latest pointer. Reset repoints latest to the seed run;
it does not delete artifacts or review history.

The publisher stages a complete directory before exposing it. Agents run at seed time and after
an applied demo update. The application read endpoint consumes published artifacts and persisted
briefs. Agent execution belongs to the application integration, not these loaders.

## SQLite ledger hooks

`app.store.ReviewLedger(database)` persists run metadata, generated or edited brief versions,
verification reports, and RM review actions. JSON artifact publication and SQLite persistence
are separate responsibilities, so the API integration registers a published run before storing
its generated briefs.

- `add_run(run_id=..., pipeline_version=..., as_of=..., source_hashes=...,
  overlay_hashes=..., is_seed=..., status=...)` registers immutable metadata. Identical retries
  succeed; changing metadata for an existing identity fails.
- `get_run(run_id)`, `list_runs()`, and `seed_run()` return run records. `seed_run()` returns the
  earliest seed registration.
- `store_brief(client_id=..., run_id=..., body=..., verification_report=...,
  origin="generated" | "rm_edited", brief_version=None)` appends a version. The ledger allocates
  consecutive version numbers under a write lock. Supplying a version requires it to be the next
  number and detects stale updates. Body and report are JSON-compatible dictionaries.
- `get_brief(client_id, run_id, brief_version=None)` returns the latest or requested version;
  `list_briefs(run_id, client_id=None)` returns all versions. Project the latest per client when
  building a view.
- `append(request, rm=..., verification_report_id=None)` stores a review. Scoped reviews must
  reference an existing client, run, and brief version. `list(run_id=None, client_id=None,
  brief_version=None)` filters review history; `client_id` and `brief_version` are keyword-only.

Missing run, seed, or brief lookups on the ledger return `None`, unlike artifact loaders.
Existing SQLite review rows migrate additively and retain their original content. Legacy JSON
review import is removed. The application must filter reviews to the active run after reset.
Section edits and synchronous re-verification belong to the API and verifier; the ledger stores
the resulting body and verification report without generating or verifying prose itself.

## Read-only application view

The view model uses the manifest's persisted `created_at` for `refreshed_at`, so repeated reads
of the same run do not change timestamps. Health checks compare base source hashes and, for an
applied overlay, its file membership and hashes under `source_dir/fixtures/update`.

Calendar extraction recognizes connected records whose `type` or `kind` is `calendar` or
`meeting`. Those records are returned unchanged. Other connected records remain in the memory
tab, and no meeting is synthesized.

A failed verification gate suppresses generated meeting-brief, insight, and Memory Card content
from the application payload. The view retains deterministic Facts, the brief version,
verification reasons, and `Needs review` when a stored draft exists. The draft remains in the
ledger for the edit endpoint and synchronous re-verification. This implements the PRD requirement
that unverified claims do not reach the RM while preserving review history.

## Commands and action contract

```sh
uv run python -m app.pipeline seed
uv run python -m app.pipeline update
uv run python -m app.pipeline reset
uv run python -m app.pipeline run --as-of 2026-08-26 --source-dir data
uv run python -m app.pipeline diff <run_a> <run_b> CL-0003
```

Equivalent `pnpm pipeline:run`, `pipeline:seed`, `pipeline:update`, `pipeline:reset`, and
`pipeline:diff` aliases accept the same arguments. `--curated-dir` and `--database` isolate
artifacts and the ledger. `run --overlay PATH` computes artifacts without invoking agents;
`update --overlay PATH` also prepares changed clients. Runtime mutations serialize with a Unix
file lock. The active pointer changes only after all required graph outputs have been saved.
Retries reuse immutable artifacts and already persisted client outputs.

`GET /api/app` performs no generation. Startup seeds an empty store, or prepares missing ledger
outputs from its existing active run. `POST /api/demo/update` accepts `{"action":"apply"}` or
`{"action":"reset"}` and returns a refreshed view. `POST /api/reviews` requires `run_id`,
`client_id`, `brief_version`, and `action` (`Approve`, `Edit`, or `Reject`). `Edit` additionally
requires `section` and `text`. It replaces the named section's text, preserves an object section's
citations, invokes verification synchronously, and appends the new version. A replacement for a
list section does not inherit its old claims' citations. Failed verification prevents approval.
Stale run/version requests return 409; unknown clients/sections return 404; malformed requests
return 422. Approve/Reject cannot carry section or replacement text.

## Remaining team integration

The infrastructure is implemented, but the default adapter is deliberately explicit about
missing team outputs. Do not treat the following placeholders as completed product behavior:

- `legacy_analytics` wraps the existing Member 4 formulas into single-number Facts. Its
  `legacy.*` formula IDs, `kind` names, and confidence mapping (high=1, medium=0.5) are transitional.
  It publishes empty Signal Sets and a context issue until Member 4's Phase A provider is wired.
  When an FX route required by the legacy engine is absent, that client's Facts are unavailable
  and the limitation is disclosed; the warning does not prevent other clients being published.
- Historical clean/filtering is tested at 2026-06-30, but historical financial computation requires
  the new analytics provider. The default legacy adapter accepts only 2026-08-26. FX normalization,
  bond nominal units, and structured-product look-through hooks are exposed by `run_pipeline`;
  their Member 4 implementations are not supplied here. Change the pipeline version when wiring
  a new provider or normalization rule, because those implementations affect run identity.
- `AgentHooks` connects Member 2 context/wealth/briefing nodes and Member 4 verification to the
  compiled graph. Default nodes produce no authored prose. The existing citation-existence gate
  is not a complete numeric or semantic verifier, so the default adapter fails readiness with an
  explicit reason. Tests inject deterministic agents and a verifier to exercise the full lifecycle.
- Connected-record and generated-section schemas remain Member 2's contract to finalize. Records
  are persisted unchanged; calendar extraction currently recognizes `type`/`kind=calendar|meeting`.
- The proposed fixture advances `CN-004` to 2026-09-01 and adds note `N-029`. The existing engine
  changes `CL-0003:fact:deadline:days` from 36 to 6 and leaves 71.5% equity versus 30% unchanged.
  The required liquidity Signal severity transition still depends on Member 4's Signal definition.

`tests/golden/CL-0003` captures the current artifact shape and inherited numerical outputs.
Run `uv run pytest tests/test_pipeline_goldens.py --update-goldens` only after reviewing the
changed values with Member 4. These goldens must be refreshed when Phase A replaces the adapter.
The frozen ownership boundary still leaves frontend consumer migration with Member 1; only
`frontend/src/generated/openapi.ts` is regenerated by this implementation.

## Review fixes and inspection

Pipeline version 2 invalidates cached runs created before the context-routing and raw-evidence
fixes. Run `pnpm pipeline:seed` after upgrading an existing store. Qualitative curated changes,
including RM notes, are recorded in `ChangeReport.changed_context_sections` and trigger the
client's generation even when financial Fact values are unchanged. `affected_signal_ids` also
includes Signals supported by changed Facts and Signals with changed score/threshold metadata.
Normalization hooks affect computational inputs; Evidence retains the original eligible raw or
overlaid source fields and physical source location.

`Ready` requires both a passing gate and the latest `Approve` decision for the current run,
client, and brief version. Generated or edited versions await review; `Reject` removes readiness.
Connected record citations resolve through `DemoViewModel.connected_evidence`, separate from the
dataset `evidence` map. Both legacy record lists and Member 2's ConnectedContext envelope are
accepted. Calendar records may use `source="calendar"` with their original `scheduled_at`.

`GET /api/clients/{client_id}/history?run_id=<optional>` exposes descending brief versions,
verification reports, associated Review Decisions, and persisted operational traces. It follows
the selected run's `prior_run_id` ancestry, so reset excludes later update runs by default.
Only verified brief content is returned; failed versions retain their version and verification
reasons. This endpoint performs no generation and does not expose model chain-of-thought.

## Communication-only refresh

With `member2_hooks` configured, `POST /api/clients/{client_id}/refresh` accepts the current
`run_id` and `brief_version`. It reads one complete communication snapshot for that client,
validates its client and as-of boundary, and generates/verifies a new pack only when the
communication content revision changes. The response includes `changed`, the resulting
`brief_version`, `communication_revision`, and `verification_report`. Fetch `/api/app` afterward
for the gated projection. A read of `/api/app` never refreshes communications.

Financial artifact files, hashes and `run_id` are unchanged. The ledger retains the original
snapshot, exact records and retrieved spans alongside the generated pack. The revision includes
record content/version and source availability, but excludes record ordering, retrieval logs and
`retrieved_at` polling timestamps. An unchanged snapshot creates no version and preserves edits
and reviews. Changed content, record deletion, or a source-availability change creates a new
version requiring fresh approval. The full verifier remains an injected data-team dependency.

A stale run or brief version returns 409; a missing client returns 404. Invalid or unavailable
snapshots or unsuccessful generation return 502 without replacing the prior brief or exposing
raw connector errors. A failed generation does not cache the new revision, so the same snapshot
can be retried after recovery. A complete candidate that fails verification is stored as a new,
unapprovable version.
A runtime without a configured communication/generation adapter returns 409. Connector loaders
must supply complete, client-scoped snapshots through the existing loader interface. Generation
consumes the exact snapshot read by refresh, without retrieving it again.

Reset keeps its existing semantics: select the seed financial run and that run's latest persisted
brief and communication revision. It does not rewind communication changes already made within
the seed run. Reset and restart do not fetch connector state; all earlier versions and reviews
remain in the history endpoint; after reset, pass an explicit `run_id` to inspect later update-run
versions. Explicit refresh is required to admit newer connector records.
