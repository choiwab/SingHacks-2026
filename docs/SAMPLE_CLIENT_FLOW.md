# Data-directory flow inspection

## Run it

```bash
uv run python -m scripts.run_client_flow --client-id CL-0003 --as-of 2026-08-26 --output data/generated/client-flow/CL-0003.json
```

The JSON includes the actual input bundle, source records, exact note spans, selected Insights,
Meeting Brief, Client Memory Card, Verification Report and node/tool trace. Generated outputs are
ignored by Git. The source CSV/JSON files are read-only and all data remains synthetic as declared
in the README. The command uses no network and does not approve the Meeting Brief.

## Current node responsibilities

| Node | Executable behavior | Observable outcome |
| --- | --- | --- |
| Context | Validate and scope dataset; publish typed Facts/Signals; read original RM notes; index exact spans; compare content versions | `context_ready`, changed Fact/Signal/record IDs in trace |
| Wealth Intelligence | Rank three supplied Signal groups; preserve scores; pair computed Facts with relevant notes | Cited discrepancy/rationale, no financial recalculation |
| RM Briefing | Build summary, discussion points, confirmation questions, dated event associations and six memory sections | Versioned Meeting Brief plus Client Memory Card |
| Evidence Gate | Check source scope, citation hashes/spans, exact Fact wording, scores, required caveats and supported prompts | Pass to review or pause with claim-specific reasons |
| Human review | Version-specific Approve/Edit/Reject/Flag interrupt; edits rerun verification | No inferred approval; stale decisions rejected |
| Finalize | Apply Review Decision and retain prior approved pack | Approved or rejected; optional review sink invoked |
| Reuse | Preserve actual previous status for identical inputs | An unchanged pending/rejected pack never becomes approved |
| Needs confirmation | Stop invalid inputs or unsupported output | Original source/claim issue and prior approved pack retained |

## Margarethe Voss-Brenner, CL-0003

Observed result: `awaiting_review`, successful verification, seven typed Facts, two original
RM notes (`N-005` and `N-006`), and three selected Insights. No Review Decision was submitted.

| Topic | Data-directory result | Why it matters for the meeting |
| --- | --- | --- |
| Portfolio changes | Luxury/consumer fund position value fell EUR 532,400; technology fund rose EUR 400,589; bond fund fell EUR 138,000, comparing 2025-12-31 with 2026-08-26 | Address the recorded concern about whether market news affects her portfolio. These are position-value changes, not flow-adjusted investment returns. |
| Suitability | Equity is 71.5% versus a 30% maximum in the household screening calculation | `N-005` records conservative risk profiling and an instruction not to make changes at that time. Confirm current intent, rather than assume permission to rebalance. |
| Funding | EUR 3.4m inheritance-tax instalment starts in 36 days; daily-liquid holdings total about EUR 17.93m | Discuss which assets could fund the payment. Do not invent a shortfall or treat liquid holdings as unencumbered cash. |

Signal scores are 100 (existing consequence component), 93 (gap), and 91 (deadline). These are
prototype discussion-priority component scores, not calibrated probabilities or investment advice.

Traceability is explicit: `CL-0003:fact:mandate-gap` resolves to the applicable mandate row and
all current holdings contributing to the allocation denominator. Change Facts cite both comparison
snapshots. `notes:N-005#<hash>:0-404` identifies the exact original note span, not an invented email.
Event associations resolve only to `data/event_log.csv` and are labelled as associations rather
than causal attribution. An event-date check prevents future events entering the Brief.

The sample opening asks to review priorities together. Follow-up prompts ask whether her willingness
to change the portfolio has changed, and which assets to review for the payment before deciding
to sell. This is an English prototype draft; her recorded reporting language is German, so
client-facing translation and wording review remain necessary.

## Additional inspection and limits

CL-0012 and CL-0019 also reach `awaiting_review` using their own Facts and RM notes. CL-0012
surfaces the long-dated Treasury position-value decline and living/medical expenses. CL-0019
surfaces family-office funding and shipping/energy context. With no allocation breach, the
suitability topic leads with concentration rather than presenting a zero gap as a breach.

The suite exercises historical date isolation, changed notes, changed financial data, joint
review, re-verification after edits, unchanged reuse and unsupported-claim rejection. Source
updates are applied only to temporary dataset copies in tests.

Known boundaries:

- Source validation covers the tables currently used by the calculators. Transactions, commitments
  and detailed structured-product underlyings are not yet incorporated into full attribution,
  deployable-liquidity calculation or scenario modelling.
- Event matching uses a simple transmission-keyword heuristic. The associations need RM inspection;
  the gate does not establish causality.
- The deterministic gate accepts exact source-backed text and constrained prompts. Novel model
  wording or unsupported RM edits pause; this is not a general semantic/compliance validator.
- Notes are `Cached`; Gmail, Teams and calendar are `Not connected`. No live MCP calls occur.
- The graph runs on invocation, not continuously. Durable checkpoint storage, concurrency control,
  the replacement dashboard API and frontend integration remain separate work.
