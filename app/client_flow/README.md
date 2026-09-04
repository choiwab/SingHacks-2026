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
│   └── briefing.py          Member 4: insight-to-brief sample agent
├── tools/
│   ├── sources.py           Member 2: read-only source tools
│   ├── projection.py        temporary adapter to the existing pipeline
│   └── evidence.py          shared citation traversal helper
└── nodes/
    ├── verification.py      Member 4: deterministic evidence gate
    └── control.py           Member 4: HLI and terminal states
```

The sample projection adapter calls the existing deterministic builder and narrows its output to
one client. Member 3 replaces that adapter with individual calculation tools only if the demo needs
it. `InMemorySaver` is sufficient for the hackathon; durable graph checkpoints remain outside this
skeleton. Member 4 owns the graph and thin API adapter; Member 1 owns the React/Fluent UI dashboard
that consumes it.
