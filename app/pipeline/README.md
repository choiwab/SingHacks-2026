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
