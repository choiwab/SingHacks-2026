# Phase A pipeline and agent handoff

The existing LangGraph Context, Wealth Intelligence, Meeting Briefing, Evidence Gate and
human-review nodes are retained. This change extends their contracts and wiring, not the dashboard
and not the financial formulas. All data is the supplied synthetic hackathon dataset.

## Dry runs

```sh
uv run python -m scripts.dry_run_agents --output data/generated/client-flow/agent-dry-run.json
uv run python -m scripts.run_client_flow --client-id CL-0003 \
  --output data/generated/client-flow/margarethe-agent.json
```

The batch command publishes or reuses one immutable Pipeline Run, pins that run for every Client,
and returns status, selected Signals, information-request codes, verification results and timing.
It exits unsuccessfully if any Client does not reach verified `awaiting_review`. It never submits
an approval. Pass `--run-id` to inspect a particular published run. A historical run is a diagnostic,
not a promise that incomplete historical data can produce a verified brief.

The individual command uses the existing persistent LangGraph runtime and SQLite memory. It
retains checkpoints and explicitly supplied local records. An optional local MCP transport uses
the same contracts. Notes remain labelled dataset/Cached, not live email or Teams messages.

## Existing pipeline runtime

```sh
uv run python -m app.pipeline seed --agents
uv run python -m app.pipeline update --agents
uv run python -m app.pipeline reset --agents
```

Use `--curated-dir` and `--database` to isolate rehearsals. The `--agents` option connects the
existing artifact runtime to the existing LangGraph through `phase_a_hooks`. Without that option,
the previous disconnected runtime behavior is preserved. Application/dashboard defaults are not
silently changed. The default bridge reads original RM notes from its pinned ArtifactStore; a
custom communication loader must return the complete pinned dataset notes plus its connected
records, with honest availability labels.

```python
from pathlib import Path
from app.pipeline.agent_bridge import phase_a_hooks
from app.pipeline.loaders import ArtifactStore
from app.pipeline.runtime import PipelineRuntime
from app.store import ReviewLedger

store = ArtifactStore(Path("data/generated/curated"))
ledger = ReviewLedger(Path("data/generated/reviews.sqlite3"))
runtime = PipelineRuntime(store, ledger, agents=phase_a_hooks(store))
runtime.seed()
ledger.close()
```

## Input and output contract

`project_agent_bundle` preserves the original Signal kind, severity, exact score, components,
threshold metadata and Evidence. It passes structured Data Quality Findings, filtering global
references to the selected Client and applicable Mandates. Original RM notes are included for
provenance, even when no financial Fact cites them. Note-only additions change memory rather than
pretending financial values changed. The run ID is provenance, not a replacement for content hashes.

The Meeting Pack retains its existing insights, brief and memory card. It now also contains
`information_requests`: stable IDs, issue codes, cited request/reason Claims, the responsible role
to contact, and conclusions that remain unsupported. These are preparation requests, not messages
sent to institutions, trade instructions, completed investigations or actual RM decisions.

Examples include original tax-lot history, complete cash-ledger reconciliation, a current valuation,
deposit withdrawal terms, full product baskets and remaining accumulator obligations. Requests and
important limitations survive even when their associated Signal is not among the selected insights.

## Selection and verification

- Financial scores and formulas are not recomputed by agents. Higher scores take precedence.
  Equal-score Signals are diversified across conversation families; repeated observations of the
  same event channel do not flood the shortlist. At most three insights are selected.
- Questions are specific to the Signal family. RM-note statements remain attributed to the note
  and require current-intent confirmation, not treated as current waiver or transaction authority.
- Phase A Fact wording is regenerated from the typed Fact, not accepted from arbitrary descriptions.
  Financial numbers in warnings are not copied into prose as uncited new calculations. Qualitative
  disclosure templates carry the limitation instead.
- The gate revalidates serialized contracts and requires the complete canonical pack: numeric
  wording, source spans, selected Signals, disclosures, request ownership and blocked conclusions.
  It rejects omitted warnings, altered units, scores, unrelated citations, future observations,
  cross-Client Evidence, changed notes and missing notes from the pinned source set.
- Cached outputs are reverified. An approval can only attach to its exact approved pack. Resuming
  human review rechecks current inputs and the gate. Policy changes invalidate generation reuse.
  Malformed stored state and unavailable inputs stop at `needs_confirmation` rather than approve.
- The artifact adapter checks duplicated presentation fields against the authoritative Meeting Pack,
  rechecks connected records and policy on approval, and refreshes stale candidates during an
  explicit preparation run. Prior versions and Review Decisions remain in the ledger.

## Boundaries

This is constrained deterministic preparation with no LLM API calls in the default path. Novel
model-generated financial wording or unrestricted RM edits do not receive an automatic pass.
The gate does not independently reconstruct bank books, prove free-language entailment, certify
bank policy or replace human suitability/tax review. Missing source data remains missing.

The dashboard integration remains the next stage. Do not present an information request as
resolved or treat a passing Evidence Gate as human approval. No live connectors are established
by these commands. Before deployment with real Client data, add the required access, retention,
encryption and operational controls.

## Validation

```sh
uv run pytest tests/test_agent_intelligence.py tests/test_agent_verification_strict.py \
  tests/test_agent_wiring.py tests/test_phase_a_agent_bridge.py
uv run pytest
uv run ruff check app tests scripts/dry_run_agents.py scripts/run_client_flow.py
```

Tests cover all Clients, the existing local MCP transports, persisted graph restarts, source
updates, policy changes, candidate edits and deliberately malformed/unsupported claims.
