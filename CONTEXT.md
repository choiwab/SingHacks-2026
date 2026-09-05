# Client Future Room

Client Future Room is the shared language for turning a private bank's raw client dataset into
defensible, reviewed preparation for a Relationship Manager's next client conversation.

## Language

### People and holdings

**Relationship Manager**:
The private-banking professional who prepares for Client conversations and retains
responsibility for every Review Decision.
_Avoid_: Advisor, operator, end user, RM user

**Client**:
A person, family, or organization whose wealth relationship and objectives are managed by a
Relationship Manager.
_Avoid_: User, account, customer

**Portfolio**:
A collection of holdings managed together under a Mandate and reporting currency. A Client may
have more than one Portfolio.
_Avoid_: Account, book

**Mandate**:
The rule set a Portfolio is measured against, expressed as allocation bands per asset class and
single-position limits.
_Avoid_: Strategy, model, profile

**Snapshot**:
The dated valuation of all holdings in a Portfolio. The dataset contains five Snapshot dates.
_Avoid_: Period, version, statement

**As-of Date**:
The date the system pretends is today. Nothing dated after it may be read, computed, or shown.
_Avoid_: Run date, today, cutoff

### Source and evidence

**Source Record**:
One row of a raw dataset file or one RM note, exactly as delivered and never edited.
_Avoid_: Raw data, input, row

**Evidence**:
A Source Record, referenced by a stable identifier, that supports a Fact, Signal, or claim shown
to the Relationship Manager.
_Avoid_: Citation link, explanation text, provenance blob

**Connected Record**:
A message, email, note, or meeting fetched read-only from an external system through a connector,
carrying its connector name, record date, retrieval time, and a state of Live, Cached, or Not
connected.
_Avoid_: Memory, RAG chunk, external data

**Data Quality Finding**:
A disclosed imperfection in the Source Records, with a severity of error (blocks publication) or
warning (disclosed and carried forward).
_Avoid_: Validation error, data issue, bug

### Computed layer

**Fact**:
A value computed deterministically from Source Records by the pipeline, carrying its formula,
inputs, Evidence, and As-of Date. Every number shown anywhere is a Fact.
_Avoid_: Metric, number, KPI, data point

**Signal**:
A condition detected from Facts against a frozen definition and threshold, such as a mandate
breach or liquidity shortfall, with severity and a deterministic priority score.
_Avoid_: Alert, flag, risk, trigger

**Curated Client Bundle**:
The single agent-consumable document describing one Client at an As-of Date: profile,
Portfolios, holdings history, Mandate, liquidity, credit, cash needs, and RM notes.
_Avoid_: Client context, client data, client JSON

**Fact Bundle**:
Every Fact computed for one Client at an As-of Date.
_Avoid_: Facts list, numbers

**Signal Set**:
Every Signal detected for one Client at an As-of Date, ranked by priority score.
_Avoid_: Alerts, findings

**Evidence Map**:
The lookup from every Evidence identifier to the exact source file, row, and fields.
_Avoid_: Evidence dict, sources, citations

**Change Report**:
The per-Client comparison of Facts and Signals between the current Pipeline Run and the prior
one, listing what was added, changed, or removed.
_Avoid_: Diff, delta, changelog

**Data Quality Report**:
Every Data Quality Finding from one Pipeline Run.
_Avoid_: Validation report, errors

**Pipeline Run**:
One deterministic execution of the pipeline over a fixed set of Source Records at one As-of
Date, identified by its inputs and pipeline version so identical inputs yield an identical run.
_Avoid_: Build, job, refresh

**Processing Mode**:
Which route a Client takes after a Pipeline Run: first seen, incremental update, or no material
change.
_Avoid_: Trigger type, state, status

**Controlled Update**:
The rehearsed change to Source Records applied during the demo to show the pipeline detecting
and propagating a change. It is reversible in one action.
_Avoid_: Demo update, mutation, fixture load

### Generated layer

**Insight**:
One of at most three client-specific observations selected by an agent from the Signal Set,
explaining what changed and why it matters to this Client, with confidence and Evidence.
_Avoid_: Alert, recommendation, finding, discrepancy card

**Meeting Brief**:
The reviewed preparation document for one Client conversation: summary, discussion topics,
"You said / Data says" discrepancy, suggested questions, and one uncertainty.
_Avoid_: Pre-read, client report, recommendation, briefing

**Client Memory Card**:
The one-glance qualitative reminder of who a Client is, generated from Connected Records: who
they are, how to communicate with them, stated needs, recent updates, open promises, and advice
notes.
_Avoid_: Memory, profile card, RAG summary

**Evidence Gate**:
The deterministic check that every number in generated content is a Fact, every claim has
Evidence, and every disclosure rule is met, before a Relationship Manager may review.
_Avoid_: Validator, verifier, critic

**Verification Report**:
The Evidence Gate's pass or fail result with reasons for one Meeting Brief and Client Memory
Card.
_Avoid_: Validation result, check output

**Review Decision**:
The Relationship Manager's recorded approval, edit, or rejection of a Meeting Brief.
_Avoid_: Feedback, action, sign-off

**Demo View Model**:
The single verified, dashboard-ready payload the interface renders. It contains only Facts,
verified generated content, Connected Records with their state, and the actions the user may take.
_Avoid_: App data, dashboard payload, projection, Monday Brief projection
