# PRD: Monday Brief

## Product statement

Monday Brief tells a Relationship Manager who needs attention, what to say, why the evidence supports it, and what changes under one scenario.
The product is deliberately limited to three screens and one live write.

## Primary user

Priscilla Ong is responsible for 20 synthetic private-banking clients across Singapore and Hong Kong booking centres.
She opens the product on Monday morning before preparing for client conversations.

## Demo objective

A judge should understand the complete value loop in under three minutes.

Two features carry the demo.

1. **Explainable Priority Calendar** turns risk, deadlines, and consequences into a Monday call and meeting plan.
2. **Evidence-backed Scenario Rehearsal** lets Priscilla practise two Strait outcomes with instant, cited ranges.

The pre-read is the necessary approval checkpoint between those features, not a separate product surface.

The recommended path is:

1. Open the Monday list and see Margarethe Voss-Brenner ranked first.
2. Open Margarethe's pre-read.
3. Read the gap between her stated risk identity and her 71.5% equity allocation.
4. Open **Why?** and inspect the exact note, holdings, and mandate rows.
5. Edit one word in the German opening and approve the pre-read.
6. Return to the list and open Abdullah Al-Mansoori.
7. Toggle between **Strait reopens** and **Strait escalates**.
8. Show that both ranges and their source trail were precomputed.

## Product principles

- No chat box.
- No generic assistant persona.
- No separate agent theatre.
- No live model call during the demo.
- No uncited generated sentence.
- No scenario point estimate.
- No external connector write.
- No action without explicit RM review.

## Screen 1: Monday list

### User question

Who needs Priscilla first?

### Required content

- All 20 clients ranked.
- Client name.
- One-line reason.
- Urgency marker with a text-equivalent priority rank.
- Upcoming meeting when connected calendar preview data exists.
- Priority score.

### Priority Calendar layout

The Monday list uses one fixed week view with no display-mode switcher.
Clients without a booked meeting appear in the ranked **Call this week** rail.
Clients with a booked meeting appear under the relevant weekday and retain their global rank.
Solid vermilion means act now, a vermilion outline means prepare next, and a charcoal outline means watch.
Together the call rail and meeting board contain exactly 20 clients.

### Ranking model

Priority is the geometric mean of gap size, deadline closeness, and consequence.
Gap size includes mandate deviation and proximity to a credit trigger.
Deadline closeness uses planned cash needs or the next known review.
Consequence includes liquidity coverage, concentration, facility pressure, risk tolerance, and transition vulnerability.
The score is an ordering aid and not a suitability decision.

### Primary demo record

Margarethe Voss-Brenner ranks first because:

- Her inherited portfolio holds 71.5% equity against a 30% Conservative mandate maximum.
- She described herself as someone who has never taken a risk with money.
- A confirmed EUR 3.4 million inheritance tax instalment begins in October 2026.
- Her recently inherited life stage and low risk tolerance increase the consequence of delay.

## Screen 2: Pre-read

### User question

What does Priscilla need for the next conversation?

### What changed

Show the three largest instrument-level value changes from 31 December 2025 to 26 August 2026.
Each line links to both snapshot rows and any event matched through primary_transmission.

### You said / Data says

Place one extracted client belief beside the most relevant confirming or contradicting fact.

For Margarethe:

- You said: “I have never taken a risk with money.”
- Data says: “Equity is 71.5% against a 30% limit.”

### Rules & money

Show no more than three items.
The ordered candidates are mandate gap, facility proximity, and the nearest cash need compared with daily-liquid assets.

### Suggested opening

Show one opening line in the client's reporting language.
The line must reference only the selected client's structured facts, beliefs, and gaps.

### Not sure yet

State the most important uncertainty before advice.
The default uncertainty is that event attribution is indicative and external assets and intent require confirmation.

### Where you left off

Show a compact read-only strip for CRM, Gmail, Teams, map context, and RM notes.
The strip must distinguish a connected record from missing context.
It must never imply that an unavailable connector was queried.

### Review actions

Priscilla can **Approve**, **Edit**, or **Reject**.
Approve and Reject write the reviewed opening and status.
Edit reveals one textarea and writes the edited opening when saved.
The review record contains client ID, action, text, RM identity, and timestamp.
This review record is the only live mutation in the demo.

## Screen 3: Scenario

### User question

How could the portfolio respond if the Strait changes course?

### Controls

The screen has one two-state toggle:

- Strait reopens.
- Strait escalates.

### Outputs

- Portfolio value-change range in base currency.
- Percentage range relative to today's portfolio.
- Three largest thematic contributions.
- A visible **not a forecast** label.
- A **Why this range?** source trail.

### Abdullah Al-Mansoori demo

The reopening scenario produces a precomputed portfolio range of approximately -7.2% to -1.4%.
The escalation scenario produces a precomputed portfolio range of approximately -1.0% to +6.5%.
The wide escalation range communicates the tension between higher shipping and energy exposures and weaker broader risk assets.

## Evidence interaction

Every **Why?** action opens one right-side drawer.
The drawer shows the computed fact, confidence, exact source file, exact source fields, RM note, and matched event record.
Evidence records are read-only.
Closing the drawer returns focus to the triggering control.

## Monday Brief projection

~~~text
CSVs and notes
    |
    v
Monday Brief projection module
    |-- facts and beliefs
    |-- gaps and priorities
    |-- constrained narration
    |-- scenario ranges
    `-- evidence
    |
    v
GET /api/monday-brief
    |
    v
React routes
~~~

The module loads, validates, and relates the consumed CSV sources and RM notes behind one interface.
Its internal stages calculate facts, extract beliefs, match gaps, rank clients, create constrained narration, and assemble scenario ranges.
The application builds one versioned projection for the explicit as-of date during FastAPI lifespan startup and saves a JSON copy for diagnostics.

### Facts and beliefs

Deterministic Python and pandas calculate holding changes, event matches, mandate gaps, facility proximity, currency-adjusted liquidity coverage, and scenario ranges.
Each fact has a stable identity, an explicit kind, text, numbers, source record identities, event identities, and confidence.
Beliefs are extracted only from RM notes and retain their note identity.

### Ranking and narration

Python pairs beliefs with structured facts and produces the ranking.
No language model performs arithmetic or scoring.
The constrained narrator receives only facts, beliefs, and gaps, not raw CSV rows.
Every output line carries Evidence, and all narration is produced before the interface is served.

### Review ledger

The web app writes Review Decisions to a local SQLite ledger.
The legacy JSON review log is imported once when present and remains untouched.
No CRM, Gmail, calendar, or meeting platform is written during the demo.

## Technical design

- Python 3.13 and pandas 3 for deterministic data transformation.
- Pydantic models define the versioned Monday Brief projection, and FastAPI exposes the projection and review interfaces.
- React 19, TypeScript, Vite, and React Router implement the three routed screens.
- TypeScript projection types are generated from FastAPI's OpenAPI document and committed.
- SQLite is authoritative for Review Decisions.
- `uv` and `pnpm` provide locked dependency installation and execution.

The startup projection writes `data/generated/app_data.json` as a diagnostic snapshot.
The React root route reads the in-memory projection once through `GET /api/monday-brief` and shares it with the pre-read and scenario routes.
Review decisions use POST /api/reviews.

## Acceptance criteria

- The Priority Calendar contains exactly 20 clients across the call rail and meeting board.
- Margarethe is ranked first with explainable score components.
- Her pre-read shows 71.5% equity against a 30% maximum.
- Her belief cites N-005.
- Her opening is in German.
- Abdullah's two scenario states update instantly without a network call.
- Scenario outputs are ranges.
- Every narrated change, rule, opening, uncertainty, and workflow status has at least one citation.
- Evidence links resolve to source records.
- Review actions persist with an RM identity and timestamp.
- The browser obtains the complete projection with one request to `GET /api/monday-brief`.
- Direct pre-read and scenario URLs load the selected Client, while invalid Client URLs return to the Monday list with an accessible notice.
- The committed TypeScript contract matches the generated FastAPI OpenAPI contract.
- No chat interface appears anywhere.
- No API credential is required.
- Desktop and mobile flows have no page-level horizontal overflow.
