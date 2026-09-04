# Member 2 implementation plan: agents, memory, and MCP

Status: Member 2 implementation completed against provisional fixtures. See
[the implementation and integration guide](../app/agents/README.md) for commands and contracts.
Real curated loaders, the final Member 4 Evidence Gate, and Member 3 persistence/API integration
remain team handoffs. Live MCP transports and neural embeddings remain deferred.

Scope: Member 2 in [the PRD](PRD_TEAMS_RM_INTELLIGENCE.md#member-2--agents--external-mcps-1-person).
This plan records the subsequent interview decisions where they refine the PRD. Financial schemas,
the changed signal fixture, review persistence, and verification rules require handoff to their
respective owners; they are not assumed to be approved by those teammates.

## Agreed decisions

| Area | Decision |
| --- | --- |
| Ownership | Member 2 owns all three agents, LangGraph orchestration, connectors, and retrieval. |
| Default execution | Deterministic and offline, with fixture inputs and deterministic narration. |
| Optional generation | OpenAI adapter; an `OPENAI_API_KEY` variable exists, but its validity has not been tested. Live execution requires explicit configuration. |
| Communication inputs | Author a small synthetic fixture set for Margarethe covering email, Teams, notes, and calendar. |
| Data dependency | Start against provisional consumer contracts and representative fixtures; Members 3–4 own the final financial schemas and values. |
| Retrieval | Topic filtering plus local TF-IDF/cosine ranking with stable tie-breaking; neural embeddings deferred. |
| Demonstrated update | One action adds a client communication and changes one data-team signal. |
| Memory-only update | Refresh relevant memory, rationale, and briefing even when portfolio facts and scores are unchanged. |
| Package migration | Hard cutover to `app/agents/` and `app/mcp/`; update imports and delete `app/client_flow/`; no compatibility shim. |
| Conflicting preferences | Preserve both dated statements and citations; ask the RM to confirm current intent. |
| Failed verification | Pause with `Needs confirmation`; expose the failed claim and reason; retain the last approved version with an update warning. |
| Approval unit | Approve the brief and Memory Card together as one versioned meeting pack. |
| Editing | Permit opening and talking-point edits, then reverify. Facts and cited memory summaries are read-only with a correction flag. |

Synthetic fixture records must be identified as authored demo material. They may display `Cached`
as their runtime availability, but must never imply that a real Gmail or Teams retrieval occurred.
Live connector recording is optional and separate from the required offline demo.

## Responsibility boundaries

| Owner | Provides | Member 2 consumes or returns |
| --- | --- | --- |
| Member 3 | Curated bundle loaders, change report, storage, review persistence, API and view-model integration | Consume versioned bundles; return graph artifacts and review events. Accept a checkpoint/persistence integration supplied by Member 3. |
| Member 4 | Financial facts, signals, deterministic scores, Evidence Gate and verification report | Consume facts/scores without recalculation; submit both generated artifacts and their evidence to the gate. |
| Member 1 | Dashboard, review controls, evidence drawer and correction-flag UI | Provide stable claim IDs, citations, pack version, availability and generation status through Member 3's boundary. |
| Member 2 | Agent state, node logic, prompts/templates, communication normalization, retrieval and graph control | Own only these implementations and their tests. |

Context assembly consumes Member 3's curated `ClientContext` as input and attaches communication
context in agent state. This distinguishes ownership of the input data contract from ownership of
the Context Agent. Agents do not parse CSVs or call the existing financial builder at runtime.

## Proposed package layout

```text
app/
  agents/
    __init__.py
    contracts.py       agent output models and provisional input contracts
    state.py           serializable LangGraph state
    graph.py           topology and injected data/gate/review boundaries
    context.py         curated input + communication context assembly
    wealth.py          signal selection and memory-linked rationale
    briefing.py        meeting brief and six-section Memory Card
    control.py         pause/resume, reuse and terminal routing
    generation.py      deterministic generation and optional OpenAI adapter
  mcp/
    __init__.py
    records.py         normalized records, provenance and source statuses
    connectors.py      fixture replay and read-only connector entry points
    retrieval.py       topic filtering, TF-IDF ranking and index refresh
tests/
  fixtures/member_2/   initial/update bundles, synthetic communications, golden outputs
  test_agents.py
  test_memory.py
  test_connectors.py
```

Use existing Pydantic and LangGraph dependencies. Keep templates close to the agent using them.
Add provider-specific connector modules only when an actual live integration is implemented.
Fixture replay is a local input adapter; it is not evidence that MCP network transport exists.

The old package mixes Member 2 work with source loading, financial building, verification, and
view-model construction. Before deletion, map every old module to its owner. Preserve reusable
data/gate code under data-team-owned modules or use their replacement; do not move those rules into
Member 2's agents. Update all known callers and tests in the same migration change.

## Minimum contracts to propose to the data team

Reuse existing fact/evidence models and identifiers where they fit. Do not create a second financial
schema simply to rename fields. Mark draft input fixtures as provisional until the data team accepts
the contract.

| Contract | Minimum contents |
| --- | --- |
| Curated input | Schema version, client ID, as-of time, bundle version, profile, facts, signals, evidence and quality report. |
| Change report | Previous/current version, changed fact/signal IDs, affected families, quality changes and processing mode. |
| Signal | Stable ID, type, fact/evidence references, precomputed priority score/components, assumptions and uncertainty. |
| Communication record | Source type, record ID/version, client ID, participants, event and retrieval times, text, provenance and availability. |
| Retrieval result | Record and chunk IDs, exact text span, topic/query, score and index version. |
| Generated claim | Stable claim ID, text, citations and authorship; cited financial values reference facts. |
| Meeting pack | Pack ID/version, client/as-of, input versions, insights, brief, Memory Card, generation mode and review status. |
| Verification/review | Exact pack version, pass/fail and failed claim IDs, editable-field changes, action and reason. |

Pack identity covers the brief, Memory Card and referenced insight/input versions. An approval for
one version cannot approve a newer version. Run logs and wall-clock retrieval timestamps are
metadata; they do not cause new content versions by themselves.

The gate must understand communication evidence as well as dataset evidence. Dates and source
metadata need their own validation; financial amounts, allocations and scores must come from the
data team. Resolve this distinction with Member 4 before integrating calendar and memory content.

## Implementation sequence

### 1. Freeze the seam and migrate the skeleton

- Publish the provisional contract examples for Members 3–4, including gate and persistence inputs.
- Preserve the current working demo while moving Member 2 code to the new packages.
- Remove raw-source paths and financial-builder calls from the new agent entry point.
- Supply local curated fixtures through the same loader boundary that Member 3 will implement.
- Update imports, package documentation, ownership labels and graph tests; remove the old package.
- Protect local secrets before any staging: `.env` is currently untracked and not ignored. Add the
  appropriate ignore rule during implementation and publish only a key-free `.env.example` if needed.

Exit: the new graph imports and runs against curated fixtures; no caller imports `app.client_flow`.

### 2. Build the synthetic communication replay and retrieval path

- Create initial and updated fixture manifests for `CL-0003`, based on the existing client timeline
  and notes `N-005` and `N-006`. New messages are explicit synthetic extensions, not source quotations.
- Use explicit client IDs and demo participants for identity mapping; do not rely on fuzzy names.
- Normalize all four source types into one record shape and preserve exact citation spans.
- Record `synthetic_fixture` provenance separately from `Cached` availability. Missing fixtures
  produce `Not connected`; required missing financial inputs stop analysis.
- Filter retrieval by client and as-of time before ranking; use topic tags, TF-IDF/cosine ranking,
  and deterministic tie-breaking for the small fixture corpus.
- Detect additions, edits and removals by stable record IDs plus content versions. Update changed
  chunks; rebuilding corpus-wide IDF weights is acceptable for this small dataset.
- Preserve conflicting dated statements. Return an explicit evidence gap when retrieval has no
  support instead of fabricating a Memory Card line.

Exit: repeatable, cited topic retrieval works with network access disabled and cannot return another
client's or a future record's content.

### 3. Implement the three agents and deterministic outputs

- Context: validate and assemble curated inputs, communication records, availability and versions.
- Wealth Intelligence: select/deduplicate up to three pipeline signals using their supplied scores;
  connect retrieved statements to facts and explain relevance without performing arithmetic.
- Briefing: compose the summary, opening, topics, questions and uncertainty, plus the six Memory Card
  sections. Each supported claim has citations; unsupported sections show insufficient evidence.
- Create communication-based conversation suggestions using both memory and fact citations where
  appropriate. Treat retrieved content as source material, never as executable instructions.
- Produce initial and updated golden meeting packs from templates and retrieved evidence.

Exit: a fixture run produces both artifacts deterministically, including financial and communication
citations, without calling an external model.

### 4. Wire changes, verification and joint review

| Input case | Agent behavior | Approval behavior |
| --- | --- | --- |
| First seen | Load full curated input and memory; generate initial pack. | Verify, then pause for review. |
| Financial change | Consume changed artifacts, rerun relevant insight selection and briefing. | New pack needs verification and approval. |
| Communication-only change | Update retrieval and relevant rationale/brief/card; preserve financial values and scores. | Changed pack needs verification and approval. |
| Combined demo update | Advance both fixture manifests together; generate updated content. | Show old/new versions and request fresh approval. |
| No relevant change | Reuse matching content and its existing status. | Never promote pending, rejected or unverified content to approved. |
| Preference conflict | Preserve both citations and highlight a confirmation item. | RM reviews the uncertainty. |
| Verification failure | Stop; show failure details and last approved pack as a prior version. | Failed content cannot reach approval. |
| RM edit | Apply opening/talking-point changes only; keep RM authorship. | Reverify the whole pack before approval. |
| Correction flag | Emit a claim-specific correction request to Member 3. | Leave the disputed fact/memory immutable; resolution produces a new pack. |

Keep prior approved and current candidate packs separate. Review requests name the pack version;
stale requests cannot approve a replacement. Graph pause/resume belongs to Member 2, the verification
implementation to Member 4, and durable review/version storage to Member 3.

For the combined update, propose a synthetic email prioritizing tax-payment planning and low
volatility. Member 4 supplies the exact changed signal and figures; do not invent a liquidity
shortfall. The current projection shows substantial liquid-asset coverage.

Exit: first seen, changed, unchanged, failure, edit, approve and reject paths work through the agreed
boundaries. Failure and correction flags do not erase the previous approved version.

### 5. Add optional live generation and complete integration

- Keep offline execution the default even when an API key exists.
- Add an OpenAI adapter using the same output contracts and retrieved evidence as the deterministic
  generator. Choose a supported model at implementation time; no model ID is assumed by this plan.
- Bound latency and retries. Missing credentials, transport failure or malformed output fall back
  to deterministic generation with the mode recorded in the trace.
- A claim that fails the Evidence Gate pauses the run; model fallback must not bypass that decision.
- Route all generated content through Member 4's gate and the same joint review.
- Integrate Member 3's real curated loaders, persistence and API; deliver example responses to Member 1.
- Defer live MCP recording until the complete required flow passes. If implemented, use read-only
  allowlisted synthetic demo accounts, record provenance, and never include credentials in fixtures.

Exit: optional generation can be unavailable without breaking the judged workflow.

## Two-day delivery order

| Window | Member 2 deliverable | Team dependency |
| --- | --- | --- |
| Day 1 morning | Provisional contracts, hard migration, fixture manifests. | M3/M4 align loader, signal, gate and review schemas. |
| Day 1 afternoon | Offline retrieval, initial three-agent run, brief and Memory Card examples. | M1 can build from examples; M4 can validate generated claims. |
| Day 1 integration | Initial pack reaches the gate and review pause. | M3 connects persistence/API; M4 supplies gate implementation. |
| Day 2 morning | Combined and memory-only updates, conflicts, joint approval and constrained edits. | M4 supplies changed signal; M3/M1 wire version-aware review. |
| Day 2 afternoon | Optional OpenAI adapter, regression checks and demo rehearsal. | Live MCP retrieval and neural embeddings remain stretch work. |

## Acceptance checks

- Hard cutover: all imports resolve, the old package is absent, and the existing demo still passes.
- Repeatability: identical fixture inputs produce identical content and pack identity offline;
  no API call occurs just because `OPENAI_API_KEY` is present.
- Retrieval: topics recover expected spans; cross-client/future records are excluded; edited records
  replace old chunks; duplicate input does not duplicate memories; missing sources disclose their status.
- Grounding: every supported claim resolves to its source, financial values remain unchanged, and
  conflicting preferences retain both dated citations.
- Updates: initial, financial-only, memory-only, combined and unchanged cases take the expected path;
  a changed pack never inherits an old approval.
- Governance: injected gate failures stop approval; both artifacts are reviewed together; only allowed
  edits pass through; prior approved content survives failures; stale review versions are rejected.
- Optional model: missing credentials, timeout and invalid structured output select the deterministic
  fallback; gate failure still pauses rather than retrying generation.
- Integration: existing Python/frontend checks and the end-to-end demo run after the migration and
  data-team integration. No live API is required for the default tests.

Completion means Margarethe's initial and updated meeting packs can be generated, inspected and
reviewed with the network disabled, with financial correctness delegated to the data team and every
communication claim traceable to an explicitly identified fixture record.
