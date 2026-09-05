# Client flow skeleton

This package mirrors the planned LangGraph flow over the split pipeline (ADR-0002). Ownership
follows PRD section 10.

```text
client_flow/
├── state.py                 Member 2: shared serializable handoff contract
├── graph.py                 Member 2: topology and conditional edges
├── agents/
│   ├── context.py           Member 2: context and change classification
│   ├── wealth.py            Member 2: fact-to-insight agent
│   └── briefing.py          Member 2: insight-to-brief agent
├── tools/
│   ├── sources.py           re-exports Member 3's pipeline hashing; one client-row reader
│   ├── projection.py        temporary adapter over app.pipeline and app.analytics
│   └── evidence.py          shared citation traversal helper
└── nodes/
    ├── verification.py      Member 4: deterministic evidence gate
    └── control.py           Member 4: HLI and terminal states (Member 3 persists reviews)
```

The adapter in `tools/projection.py` loads and validates the raw sources through
`app.pipeline.sources`, computes facts through `app.analytics.facts.fact_engine`, and narrows the
result to one client. It selects no insights and writes no prose. It is temporary until Member 3's
published artifact loaders (issue #23) land, at which point the agents read curated artifacts
instead of recomputing the book. `InMemorySaver` is sufficient for the hackathon; durable graph
checkpoints remain outside this skeleton. Member 2 compiles the graph; Member 3 owns the API that
invokes it and persists review decisions; Member 1 owns the React dashboard that consumes it.
