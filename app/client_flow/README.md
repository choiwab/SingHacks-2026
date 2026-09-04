# Client flow skeleton

This package mirrors the planned LangGraph flow without duplicating the working Monday Brief
pipeline.

```text
client_flow/
├── state.py                 shared serializable handoff contract
├── graph.py                 topology and conditional edges
├── agents/
│   ├── context.py           Member 2: context and change classification
│   ├── wealth.py            Member 3: fact-to-insight sample agent
│   └── briefing.py          Member 3: insight-to-brief sample agent
├── tools/
│   ├── sources.py           Member 2: read-only source tools
│   ├── projection.py        temporary adapter to the existing pipeline
│   └── evidence.py          shared citation traversal helper
└── nodes/
    ├── verification.py      Member 4: deterministic evidence gate
    └── control.py           Member 4: HLI and terminal states
```

The sample projection adapter calls the existing deterministic builder and narrows its output to
one client. Replace that adapter with individual calculation tools only when Members 2 and 3 split
the production implementation. `InMemorySaver` is sufficient for the hackathon; durable graph
checkpoints and API wiring remain intentionally outside this skeleton.
