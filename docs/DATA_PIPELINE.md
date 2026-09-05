# Reviewed EDA to automated data pipeline

## Run

```sh
uv sync --group dev
uv run python -m app.pipeline run --source-dir data --as-of 2026-08-26
uv run python -m scripts.run_client_flow --client-id CL-0003 --output data/generated/client-flow.json
```

The first command publishes the entire Client book. The second consumes the same content-addressed
Phase A calculations, builds a cited Meeting Brief using the existing agent graph and persistent
memory, and stops for a human Review Decision. Neither command needs an LLM API key. The source
dataset is synthetic. Gmail, Teams and calendar are not magically connected by running a pipeline.

For another input directory or an isolated rehearsal:

```sh
uv run python -m app.pipeline run --source-dir /path/to/csv-directory \
  --curated-dir /path/to/output --as-of 2026-08-26
uv run python -m app.pipeline seed --curated-dir /tmp/curated --database /tmp/reviews.sqlite3
uv run python -m app.pipeline update --curated-dir /tmp/curated --database /tmp/reviews.sqlite3
uv run python -m app.pipeline reset --curated-dir /tmp/curated --database /tmp/reviews.sqlite3
```

`seed/update/reset` use the existing application runtime. Its default brief-generation hooks remain
disconnected, and its citation-only fallback never grants review readiness. Use `run_client_flow`
for the wired deterministic agent graph with constrained-wording verification. This distinction is
intentional: a data publication is not a client-approved recommendation or a connected dashboard.

## Processing layers

1. **Ingest:** read the eleven CSV files and `rm_notes.json` using their checked source schemas.
   Missing files, invalid types, duplicate keys, orphan references and invalid FX fail explicitly.
   Controlled Updates upsert complete rows in memory, never overwrite the original Source Records.
2. **Clean:** remove future observations and dated future columns before analytics. Preserve dates
   of known future cash needs. Generate an exact-snapshot FX table and quantity-times-price
   reconciliation table. Bond quantities already use the dataset's price-quotation units, so there
   is no blanket division by 100. Never invent FX, cost bases, trade lots or missing basket names.
3. **Compute:** `app/analytics/phase_a*.py` supplies the reviewed deterministic formulas. Holdings
   remain authoritative reported snapshots, not a ledger reconstructed from transactions.
   Performance, separate gross receipts/fees, mandates, canonical funding obligations, issuer
   exposure, collateral, currency exposure, event associations and conservative suitability are
   computed before any agent is called. Facts carry formula identifiers, inputs, dates and Evidence.
4. **Validate and publish:** require unique Fact/Signal identities and resolvable Evidence before
   atomically publishing immutable JSON artifacts. Data Quality Findings disclose known source
   limitations. `latest.json` changes only after a complete run is available.
5. **Consume:** agents read a pinned run through `ArtifactStore` and `project_agent_bundle`.
   They select already-scored Signals; they do not recompute the financial values. The Evidence
   Gate checks exact Facts, source spans and constrained wording. Human review remains mandatory.

```python
from pathlib import Path
from app.pipeline.runner import run_pipeline
from app.pipeline.loaders import ArtifactStore
from app.pipeline.agent_projection import project_agent_bundle

root = Path("data/generated/curated")
manifest = run_pipeline(curated_dir=root)
store = ArtifactStore(root)
bundle = project_agent_bundle(store, "CL-0003", manifest.run_id)
```

Do not combine separately loaded `latest` artifacts across an update. Pin `manifest.run_id` for
the entire invocation. `app.pipeline.agent_inputs.load_curated_bundle` is the automatic raw-source
entry point used by the existing agent/MCP runtime; it may create or reuse artifacts. In contrast,
`ArtifactStore` and `project_agent_bundle` only read already-published artifacts.

## Financial guardrails

- Same-store reported-mark changes exclude additions and their own post-purchase moves. They are
  not TWR, money-weighted return or total investment return. Income, fees and financing interest
  are separately reported using observed FX and are not reconciled to positions.
- Managed Portfolio allocation tests cover all six classes, including zero holdings. Custody is
  not subjected to managed allocation bands. Note-based exceptions retain the source note and
  require confirmation, not a claim that the bank granted a legal waiver.
- Funding distinguishes confirmed/likely baseline needs from conditional and aspirational needs,
  avoids double-counting documented commitment links, and separates deposit-inclusive cash from
  immediately available daily cash. Historical undated commitment balances are unavailable, not
  silently backdated. Missing information is not zero liquidity risk.
- Structured-product issuer exposure uses full market value for each mapped leg and is
  non-additive across issuers. It is not derivative notional or a validated execution price.
  Unnamed baskets remain unknown. Currency screens assume unhedged exposure, not known hedges.
- Collateral trajectory is distinct from current LTV breach. Event exposure indicates an
  association, not causation or hedge effectiveness. Income-oriented suitability screens do not
  estimate volatility from five snapshots. Inherited transfer prices do not establish tax basis.

## Versioning, speed and operating cost

`notebooks/reference_maps.json` is the single version-controlled map shared with the notebook.
It records its effective date and pending responsible-human approval. Historical runs withhold
map-dependent claims before that date. No agent review is represented as actual human RM signoff.

The default run identity includes raw file hashes, overlay hashes, As-of Date, implementation
fingerprints and map bytes. Changing a policy or formula invalidates the cache even without a Git
commit. Identical inputs skip CSV parsing and financial computation. Files are rechecked before
publication, so concurrent changes fail with a retry instruction rather than publish mixed inputs.
Custom analytics/normalization providers must supply a distinct `pipeline_version` when changed.

No notebook, plotting library, vector database, external service or paid model is needed for data
processing. The current batch is small and runs in one Python process, avoiding per-Client workers
and infrastructure overhead. JSON is deliberately retained for compatibility and inspectable
Evidence, not claimed to be an optimal format for arbitrarily large bank datasets.

Measured locally on the supplied dataset: 20 Clients, 1,553 Facts and 177 Signals published in
1.97 seconds from an empty output store; an identical cached run took 0.004 seconds. These are
single-run observations with a warm Python process, not latency guarantees or large-book benchmarks.
All 20 Clients also completed the actual deterministic agent graph and its Evidence Gate, stopping
at `awaiting_review` with no automatic human approval.

For scheduling, invoke the idempotent `run` command after upstream files are delivered atomically
or on a scheduler controlled by your deployment. Do not write individual source files while a run
is reading them. A failed command leaves the last published run available. Configure access
controls, encryption, retention and operational alerting before using real banking data.

## Validation

```sh
uv run pytest tests/test_phase_a_core.py tests/test_phase_a_risk.py \
  tests/test_phase_a_review.py tests/test_phase_a_pipeline.py
uv run pytest
uv run ruff check app tests
```

The original compatibility adapter remains explicitly available as `legacy_analytics` and
`load_legacy_curated_bundle`; it is not the reviewed default. Legacy golden fixtures document that
adapter only. The Phase A tests check reviewed values, Evidence, temporal restrictions, policy
cache invalidation and raw-source-to-agent contract integration.
